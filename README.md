<<<<<<< HEAD
# Kalkulator czasu ukończenia półmaratonu

Aplikacja szacuje przewidywany czas ukończenia półmaratonu na podstawie płci, wieku i czasu na 5 km, które użytkownik podaje w formie swobodnego
opisu tekstowego - dane wyciąga za niego Ai .

## Architektura

```
dane CSV (surowe) -> preprocess_time.py  (czas tekstowy -> sekundy)

dane CSV (oczyszczone)  upload_to_r2.py -> Cloudflare R2 (bucket) -> notebooks/train_pipeline.ipynb (czyszczenie + PyCaret + zapis modelu) -> zapis modelu lokalnie [models/*.pkl (lokalnie)] i do r2 models/latest.pkl -> app/streamlit_app.py (pobiera model, LLM wyciąga dane z tekstu, liczy predykcję) ->  Langfuse (metryki działania LLM)

```

## Struktura projektu

```
polmaraton-app/
├── data/
│   ├── raw/              # tu wrzucamy swoje surowe pliki CSV
│   └── processed/        # tu trafiają pliki po konwersji czasu na sekundy
├── src/
│   ├── preprocess_time.py  # krok 1: konwersja czasu tekstowego na sekundy
│   ├── upload_to_r2.py     # krok 2: wysyłk danych do Cloudflare R2
│   └── r2_management.py         # wspólne funkcje do R2 (używane też przez notebook i aplikacje)
├── notebooks/
│   └── train_pipeline.ipynb  # krok 3: pipeline trenowania modelu (PyCaret)
├── app/
│   ├── llm_extract.py      # wyciąganie danych z tekstu przez OpenAI + Langfuse
│   └── streamlit_app.py    # krok 4: aplikacja Streamlit
├── models/                 # lokalna kopia wytrenowanych modeli
├── requirements.txt
├── .env            # przykład zmiennych środowiskowych (do lokalnego użycia)
└── .streamlit/secrets.toml  # przykład sekretów dla Streamlit Community Cloud
```

## Krok po kroku

### 1. Przygotowanie danych (konwersja czasu na sekundy)

1. Wrzuć swoje surowe pliki CSV do `data/raw/` (np. `halfmarathon_wroclaw_2024__final.csv`).
2. Uruchom:

   ```bash
   python src/preprocess_time.py
   ```

   Skrypt doda do plików nowe kolumny z czasem zapisanym jako liczba sekund
   (`"5 km Czas (s)"`, `"10 km Czas (s)"`, `"15 km Czas (s)"`, `"20 km Czas (s)"`,
   `"Czas (s)"`) i zapisze wynik w `data/processed/`.

   > Domyślne nazwy kolumn (`TIME_COLUMNS` w `src/preprocess_time.py`) są już
   > dopasowane do pliku `halfmarathon_wroclaw_2024__final.csv`. Jeśli użyjesz
   > pliku z innej edycji biegu, sprawdź `df.columns` i w razie potrzeby
   > popraw tę listę.

### 2. Wysyłka danych do Cloudflare R2


```bash
python src/upload_to_r2.py
```

Pliki trafią do bucketu pod prefiksem `data/`.

### 3. Trenowanie modelu (notebook + PyCaret)

```
jupyter notebook notebooks/train_pipeline.ipynb
```

Uruchomiono komórki po kolei. Notebook:
- pobiera dane z R2,
- czyści je (usuwa braki i wartości odstające),
- trenuje kilka modeli regresji za pomocą PyCaret i wybiera najlepszy
  (metryka: **MAE** - średni błąd w sekundach),
- zapisuje model lokalnie w `models/` i wysyła go do R2 jako
  `models/latest.pkl` (plus wersja z datą w nazwie- historyczne).
  

### 4. Uruchomienie aplikacji lokalnie

```bash
streamlit run app/streamlit_app.py
```

Otworzy się przeglądarka z formularzem tekstowym. Wpisz np.:

"Cześć,mam na imie Tomek, jestem mężczyzną i mam 25 lat. Na 5 km mam czas 26 minut"

Aplikacja wyciągnie z tego płeć/wiek/czas, sprawdzi czy niczego nie brakuje, 
jeśli tak to wskaże, które dane należy jeszcze podać, a jeśli mamy komplet - pokaże przewidywany czas półmaratonu.

