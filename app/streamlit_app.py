"""
streamlit_app.py

To jest KROK 4 z naszego zadania: aplikacja webowa (Streamlit), która:
1. Pyta użytkownika o krótki opis siebie (tekst dowolny, np. "Cześć, mam 30 lat...").
2. Za pomocą LLM (OpenAI) wyciąga z tego tekstu: płeć, wiek i czas na 5 km.
3. Jeśli czegoś brakuje - mówi użytkownikowi czego dokładnie.
4. Jeśli mamy komplet danych - wczytuje wytrenowany model (PyCaret) i pokazuje
   przewidywany czas ukończenia półmaratonu.

Uruchomienie lokalnie:
    streamlit run app/streamlit_app.py

"""

# "os" - zmienne środowiskowe i ścieżki do plików
import os

import sys
# "sys" - potrzebny, żeby dodać nasz folder src/ do listy miejsc,
# w których Python szuka modułów do zaimportowania
import streamlit as st

# --- Sekrety (klucze API) ---
# Lokalnie trzymamy klucze w pliku .env (biblioteka python-dotenv je stamtąd
# czyta). Ale po wdrożeniu na Streamlit Community Cloud nie ma tam pliku .env
# - zamiast tego sekrety wpisuje się w panelu "Settings -> Secrets", a Streamlit
# udostępnia je w Pythonie przez st.secrets.
#
# Poniższa pętla przepisuje WSZYSTKIE sekrety z st.secrets do zmiennych
# środowiskowych (os.environ), żeby reszta naszego kodu (np. biblioteka OpenAI
# czy boto3) mogła z nich korzystać w JEDEN, standardowy sposób - bez
# sprawdzania za każdym razem "czy jesteśmy lokalnie, czy w chmurze".
try:
    # st.secrets.items() zwraca pary (klucz, wartość) ze wszystkich sekretów
    for key, value in st.secrets.items():
        # setdefault() ustawia wartość tylko jeśli dana zmienna jeszcze
        # nie istnieje - dzięki temu nie nadpiszemy przypadkiem czegoś,
        # co już wcześniej ustawiliśmy inną metodą.
        os.environ.setdefault(key, str(value))
except FileNotFoundError:
    # Jeśli pracujemy lokalnie i nie mamy pliku .streamlit/secrets.toml,
    # Streamlit rzuci właśnie ten błąd - to nie jest prawdziwy problem,
    # bo zaraz i tak wczytamy klucze z pliku .env (linijki niżej).
    pass

# load_dotenv() wczytuje zmienne z pliku .env (np. OPENAI_API_KEY) - to jest
# nasze główne źródło kluczy podczas pracy lokalnej.
from dotenv import load_dotenv
load_dotenv()

# Domyślnie Python szuka modułów do zaimportowania tylko w tym samym folderze
# co plik uruchamiany. Nasz plik r2_management.py leży w folderze src/, a nie app/,
# więc musimy dopisać src/ do listy miejsc przeszukiwanych przez Pythona.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

# Importy muszą być na górze pliku wg konwencji Pythona (PEP8), ale te trzy
# poniżej muszą być po sys.path.append() (inaczej Python by ich nie znalazł) -
# stąd komentarz "noqa: E402", który mówi narzędziom sprawdzającym, że zrobiono to celowo".
from r2_management import download_file  # noqa: E402
from llm_extract import extract_runner_data, find_missing_fields, find_invalid_fields  # noqa: E402
from pycaret.regression import load_model, predict_model  # noqa: E402
import pandas as pd  # noqa: E402


# --- Konfiguracja strony ---
# set_page_config() ustawia tytuł karty przeglądarki i ikonkę (favicon)
st.set_page_config(page_title="Kalkulator czasu półmaratonu", page_icon=":runner:")
st.title(":runner: Kalkulator czasu ukończenia półmaratonu")
st.write(
    "Opisz siebie własnymi słowami - podaj swoją płeć, wiek oraz czas, "
    "w jakim biegasz 5 km. Nasz model oszacuje Twój przewidywany czas "
    "na półmaratonie."
)


@st.cache_resource
def load_prediction_model():
    """
    Pobiera najnowszą wersję modelu z Cloudflare R2 (jeśli jeszcze nie mamy jej
    zapisanej lokalnie) i wczytuje ją za pomocą PyCaret, gotową do liczenia
    przewidywań (predykcji).
    """
    # PyCaret sam dopisuje rozszerzenie ".pkl" do nazwy pliku modelu,
    # dlatego tutaj podajemy ścieżkę bez tego rozszerzenia.
    local_model_path = "models/latest"

    # Sprawdzamy, czy model jest już zapisany lokalnie (np. z poprzedniego
    # uruchomienia aplikacji) - jeśli tak, nie pobieramy go ponownie z R2,
    # żeby zaoszczędzić czas i transfer danych.
    if not os.path.exists(local_model_path + ".pkl"):
        bucket_name = os.environ["R2_BUCKET_NAME"]
        download_file(bucket_name, "models/latest.pkl", local_model_path + ".pkl")

    # load_model() z PyCaret wczytuje cały "pipeline" modelu (razem z krokami takimi jak kodowanie płci czy normalizacja liczb).
    return load_model(local_model_path)


def seconds_to_hms(total_seconds: float) -> str:
    """
    Zamienia liczbę sekund (np. 6330) na czytelny tekst w formacie GG:MM:SS
    (np. "01:45:30"). To jest odwrotność funkcji time_to_seconds()
    z pliku src/preprocess_time.py.
    """
    # round() zaokrągla do najbliższej liczby całkowitej (model może zwrócić
    # np. 6330.42, a sekundy muszą być liczbą całkowitą)
    total_seconds = int(round(total_seconds))

    # Dzielenie całkowite (//) i reszta z dzielenia (%) to standardowy
    # sposób na rozbicie sekund na godziny/minuty/sekundy
    hours = total_seconds // 3600            # ile pełnych godzin mieści się w sekundach
    minutes = (total_seconds % 3600) // 60    # ile pełnych minut zostaje po odjęciu godzin
    seconds = total_seconds % 60              # ile sekund zostaje na końcu

    # f-string z formatowaniem "02d" oznacza "liczba całkowita, zawsze
    # na 2 cyfrach, z zerem wiodącym jeśli trzeba" - np. 5 -> "05"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# --- Formularz wejściowy ---
# st.text_area() tworzy pole tekstowe, w którym użytkownik może wpisać dłuższy tekst 
user_text = st.text_area(
    "Przedstaw się:",
    placeholder=(
        "Np. Cześć, mam na imię Kasia, mam 34 lata, jestem kobietą "
        "i mój ostatni czas na 5 km to 26 minut."
    ),
    height=120,
    max_chars=1000,
    help="Podaj płeć, wiek oraz czas na 5 km. Maksymalnie 1000 znaków.",
)

if st.button("Oszacuj mój czas", type="primary"):
    #type="primary" – Przycisk ma wyróżniające się, pełne tło, co przyciąga wzrok jako najważniejszy krok do kliknięcia.   
    # Sprawdzamy, czy użytkownik w ogóle coś wpisał (strip() usuwa spacje
    # z początku/końca tekstu, żeby sam "enter" czy spacje się nie liczyły)
    if not user_text.strip():
        st.warning("Najpierw wpisz coś o sobie w polu powyżej 🙂")
        # st.stop() natychmiast przerywa wykonywanie reszty skryptu
        st.stop()

    # --- Krok 1: wyciągamy dane z tekstu za pomocą LLM ---
    # st.spinner() pokazuje użytkownikowi "kręcące się kółko" i tekst,
    # dopóki kod wewnątrz bloku "with" się nie wykona - dzięki temu
    # użytkownik wie, że aplikacja coś robi, a nie że się zawiesiła
    with st.spinner("Analizuję Twój opis..."):
        extracted_data = extract_runner_data(user_text)

    # --- Krok 2: sprawdzamy, czy mamy komplet danych ---
    missing_fields = find_missing_fields(extracted_data)

    # Jeśli lista brakujących pól NIE jest pusta (czyli czegoś brakuje)...
    if missing_fields:
        st.error(
            "Brakuje mi niektórych informacji, żeby oszacować Twój czas. "
            # ", ".join(lista) skleja elementy listy w jeden tekst, oddzielony
            # przecinkami, np. ["wiek", "płeć"] -> "wiek, płeć"
            f"Dopisz proszę: **{', '.join(missing_fields)}**."
        )
        # Pokazujemy też co udało się rozpoznać, żeby użytkownik widział,
        # że aplikacja faktycznie coś zrozumiała, a nie tylko wyświetla błąd
        st.json(extracted_data)
        st.stop()  # kończymy tutaj - nie ma sensu liczyć predykcji bez kompletu danych
    # --- Krok 2b: sprawdzamy, czy wartości są realistyczne ---
    # Robimy to dopiero po sprawdzeniu braków, bo find_invalid_fields
    # zakłada, że żadna wartość nie jest None.
    invalid_fields = find_invalid_fields(extracted_data)

    if invalid_fields:
        st.error(
            "Podane dane wyglądają nierealnie: "
            f"{'; '.join(invalid_fields)}. Popraw opis i spróbuj ponownie."
        )
        st.stop()    
    # --- Krok 3: mamy komplet danych - przygotowujemy je w formie, jakiej
    # oczekuje nasz model (czyli DOKŁADNIE tych samych nazw kolumn, których
    # użyliśmy w notebooku podczas trenowania: gender, age, time_5km_s) ---
    input_df = pd.DataFrame([{
        "gender": extracted_data["gender"],
        "age": extracted_data["age"],
        "time_5km_s": extracted_data["time_5km_seconds"],
    }])

    st.success("Rozpoznane dane:")
    st.write(
        f"- Płeć: **{extracted_data['gender']}**\n"
        f"- Wiek: **{extracted_data['age']} lat**\n"
        f"- Czas na 5 km: **{seconds_to_hms(extracted_data['time_5km_seconds'])}**"
    )

    # --- Krok 4: wczytujemy model i liczymy predykcję ---
    with st.spinner("Wczytuję model i liczę przewidywanie..."):
        model = load_prediction_model()
        # predict_model() z PyCaret bierze nasz DataFrame z danymi wejściowymi
        # i zwraca go z DODATKOWĄ kolumną zawierającą przewidywanie modelu
        prediction = predict_model(model, data=input_df)

    # PyCaret zapisuje wynik przewidywania w kolumnie "prediction_label".
    # .iloc[0] bierze wartość z PIERWSZEGO (i jedynego) wiersza naszej tabeli.
    predicted_seconds = prediction["prediction_label"].iloc[0]

    # st.metric() wyświetla dużą, wyróżnioną liczbę/wartość - idealne
    # do pokazania "głównego wyniku" naszej aplikacji
    st.metric(
        label="Przewidywany czas ukończenia półmaratonu",
        value=seconds_to_hms(predicted_seconds),
    )

    # st.caption() wyświetla mały, wyszarzony tekst - dobry na zastrzeżenia/uwagi
    st.caption(
        "To jest tylko szacunek statystyczny na podstawie danych historycznych "
        "innych biegaczy - Twój faktyczny wynik zależy też od formy w dniu startu, "
        "pogody, trasy i wielu innych czynników. Powodzenia! 🎉"
    )
