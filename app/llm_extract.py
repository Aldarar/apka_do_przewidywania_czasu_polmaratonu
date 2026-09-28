"""
llm_extract.py

Ten moduł odpowiada za wyciągnięcie z dowolnego tekstu użytkownika
(np. "Cześć, mam na imię Ola, mam 29 lat, jestem kobietą i biegam
5km w 27 minut") trzech konkretnych wartości, których potrzebuje nasz
model:
    - gender          ("M" albo "K")
    - age             (wiek w latach, liczba)
    - time_5km_seconds (czas na 5 km w SEKUNDACH, liczba)

Do tego używamy modelu OpenAI z tzw. "structured output" (JSON schema) -
to znaczy, że z góry mówimy modelowi DOKŁADNIE jakiego kształtu odpowiedź
ma nam dać, a on się do tego stosuje. Dzięki temu zawsze dostajemy
przewidywalny JSON, a nie luźny tekst, który trzeba by ręcznie parsować
(np. zgadywać, czy model napisał "29 lat" czy po prostu "29").

Całość jest spięta z Langfuse (przez dekorator @observe), żeby zbierać
metryki: ile razy LLM się pomylił, ile kosztował, jak długo trwało
zapytanie itd. - to wszystko trafia do panelu na cloud.langfuse.com.
"""

# "os" - do odczytu zmiennych środowiskowych (klucz API do OpenAI)
import os

# "json" - do zamiany tekstu JSON (który dostajemy od OpenAI) na słownik Pythona
import json

# Oficjalna biblioteka OpenAI
from openai import OpenAI

# @observe to "dekorator" z Langfuse - w Pythonie dekorator to specjalny
# zapis "@coś" nad definicją funkcji, który "opakowuje" tę funkcję dodatkowym
# zachowaniem, bez konieczności zmieniania kodu wewnątrz niej.
from langfuse.decorators import observe, langfuse_context

# Tworzymy klienta OpenAI. Klucz API jest brany AUTOMATYCZNIE ze zmiennej
# środowiskowej OPENAI_API_KEY (czyli z pliku .env albo z sekretów Streamlit).
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# EXTRACTION_SCHEMA to "przepis" (JSON Schema) opisujący dokładnie, jakiego
# kształtu JSON oczekujemy od modelu OpenAI. Dzięki temu model NIE MOŻE
# odpowiedzieć w innym formacie - np. nie doda dodatkowych pól, nie pomyli
# nazw kluczy, nie napisze zwykłego zdania zamiast JSON-a.
EXTRACTION_SCHEMA = {
    "name": "runner_data",
    "schema": {
        "type": "object",  # odpowiedź ma być JSON-owym "obiektem" (czyli słownikiem)
        "properties": {
            # Każde pole niżej opisuje jedną wartość, którą chcemy dostać
            "gender": {
                "type": ["string", "null"],   # albo tekst, albo "brak danych" (null)
                "enum": ["M", "K", None],      # dopuszczamy TYLKO te 3 wartości
                "description": "Płeć osoby: 'M' dla mężczyzny, 'K' dla kobiety. null jeśli nie podano.",
            },
            "age": {
                "type": ["integer", "null"],   # liczba całkowita albo null
                "description": "Wiek osoby w latach. null jeśli nie podano.",
            },
            "time_5km_seconds": {
                "type": ["integer", "null"],
                "description": (
                    "Czas biegu na 5 km, PRZELICZONY NA SEKUNDY. "
                    "Np. '27 minut' -> 1620, '25:30' -> 1530. null jeśli nie podano."
                ),
            },
        },
        # "required" mówi: te 3 klucze MUSZĄ się znaleźć w odpowiedzi
        # (choć ich wartość może być null, jeśli czegoś nie znaleziono w tekście).
        "required": ["gender", "age", "time_5km_seconds"],
        # "additionalProperties": False zabrania modelowi dodawania
        # jakichkolwiek dodatkowych, niezaplanowanych przez nas pól.
        "additionalProperties": False,
    },
    "strict": True,  # "strict" wymusza, żeby OpenAI TRZYMAŁ SIĘ schematu
}

# SYSTEM_PROMPT to instrukcja, którą wysyłamy do modelu PRZED tekstem
# użytkownika - mówimy mu "jaką rolę ma pełnić" i jak ma się zachować.
# Potrójne cudzysłowy (""" ... """) pozwalają napisać tekst na wielu liniach.
SYSTEM_PROMPT = """\
Jesteś asystentem, który wyciąga konkretne dane z opisu biegacza podanego \
w dowolnej, swobodnej formie. Interesują Cię wyłącznie 3 informacje:
1. płeć (M/K),
2. wiek w latach,
3. czas na dystansie 5 km, przeliczony na SEKUNDY.

Jeśli którejś informacji brakuje w tekście, zwróć dla niej null - nie zgaduj \
i nie wymyślaj wartości. Jeśli czas jest podany w minutach (np. "27 minut" \
albo "biegam 5km w 27 min"), przelicz go dokładnie na sekundy.
"""


# Dekorator @observe() z Langfuse automatycznie "opakowuje" funkcję poniżej.
# Dzięki temu nie musimy sami pisać kodu do mierzenia czasu czy logowania -
@observe(name="extract_runner_data")
def extract_runner_data(user_text: str) -> dict:
    """
    Wysyła tekst użytkownika do modelu OpenAI i zwraca słownik (dict) z
    wyciągniętymi danymi, np.:

        {"gender": "K", "age": 29, "time_5km_seconds": 1620}

    Wartości, których model nie znalazł w tekście, będą miały wartość None
    (odpowiednik "null" z JSON-a w Pythonie).
    """

    # client.chat.completions.create() to właściwe wywołanie modelu OpenAI -
    # wysyłamy "rozmowę" (messages) i dostajemy odpowiedź.
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        # Tutaj mówimy modelowi: "odpowiedz w formacie JSON, dokładnie
        # według schematu EXTRACTION_SCHEMA zdefiniowanego wyżej"
        response_format={"type": "json_schema", "json_schema": EXTRACTION_SCHEMA},
    )

    # Model zwraca odpowiedź jako TEKST wyglądający jak JSON, np.:
    #   '{"gender": "K", "age": 29, "time_5km_seconds": 1620}'
    # Musimy go "sparsować" (zamienić z tekstu na prawdziwy słownik Pythona),
    # żeby móc się do niego odwoływać jak do zwykłego słownika (np. data["age"]).
    raw_content = response.choices[0].message.content
    extracted_data = json.loads(raw_content)

    # Dopisujemy do "obserwacji" w Langfuse dodatkowe informacje, przydatne
    # przy analizie w panelu - surowy tekst wejściowy oraz to, co udało się
    # wyciągnąć. Dzięki temu w Langfuse od razu widać "wejście -> wyjście"
    # dla każdego zapytania, bez klikania w szczegóły.
    langfuse_context.update_current_observation(
        input=user_text,
        output=extracted_data,
    )

    return extracted_data


def find_missing_fields(extracted_data: dict) -> list:
    """
    Sprawdza, których danych brakuje w tym, co wyciągnął model, żeby móc
    poinformować o tym użytkownika w aplikacji (np. "brakuje mi: wieku").

    Zwraca listę czytelnych, polskich nazw brakujących pól - np. ["wiek"].
    Jeśli niczego nie brakuje, zwraca pustą listę [].
    """
    # Słownik "techniczna nazwa pola" -> "ludzka nazwa po polsku",
    # żeby komunikat dla użytkownika brzmiał naturalnie, a nie np. "age".
    field_labels = {
        "gender": "płeć",
        "age": "wiek",
        "time_5km_seconds": "czas na 5 km",
    }

    missing = []  # tutaj będziemy zbierać brakujące pola

    # Przechodzimy po każdym polu, które model miał wypełnić
    for field_key, label in field_labels.items():
        # .get(field_key) bezpiecznie odczytuje wartość ze słownika -
        # jeśli klucza by nie było, zwróci None zamiast wywalić błąd.
        value = extracted_data.get(field_key)

        if value is None:
            # Model nie znalazł tej informacji w tekście użytkownika
            missing.append(label)

    return missing

# Dopuszczalne zakresy - dopasuj do swoich danych treningowych (patrz niżej)
MIN_AGE, MAX_AGE = 16, 90
MIN_TIME_5KM, MAX_TIME_5KM = 900, 3600   # 15 min - 60 min, w sekundach


def find_invalid_fields(extracted_data: dict) -> list:
    """
    Sprawdza, czy wartości, które model wyciągnął z tekstu, mieszczą się
    w realistycznych granicach. Zwraca listę komunikatów dla użytkownika
    (pusta lista = wszystko OK).

    Uwaga: wywołanie następuję po find_missing_fields(), bo zakłada, że
    żadna wartość nie jest None.
    """
    problems = []

    age = extracted_data.get("age")
    if age is not None and not (MIN_AGE <= age <= MAX_AGE):
        problems.append(f"wiek musi być w zakresie {MIN_AGE}-{MAX_AGE} lat")

    time_5km = extracted_data.get("time_5km_seconds")
    if time_5km is not None and not (MIN_TIME_5KM <= time_5km <= MAX_TIME_5KM):
        problems.append(
            f"czas na 5 km musi być w zakresie "
            f"{MIN_TIME_5KM // 60}-{MAX_TIME_5KM // 60} minut"
        )

    return problems