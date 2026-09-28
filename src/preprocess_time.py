"""
preprocess_time.py

To krok 1 tego projektu
Ten skrypt bierze surowe pliki CSV z wynikami półmaratonów (np. eksport
z systemu pomiaru czasu) i:
1. wczytuje je do pandas
2. zamienia kolumny z czasami zapisanymi jako tekst (np. "01:45:30") na liczbę sekund (np. 6330)
3. zapisuje oczyszczone pliki do folderu data/processed.

Nazwy kolumn w plikach CSV mogą się różnić od tych poniżej.
Sprawdź jak nazywają się `df.columns` na swoim pliku, żeby zobaczyć jak
faktycznie nazywają się kolumny, i popraw listę TIME_COLUMNS.
"""

import os
import pandas as pd

# Folder, w którym trzymasz surowe pliki CSV (tak jak je pobrałeś)
RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# Folder, do którego zapisuję już oczyszczone pliki
PROCESSED_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

# Lista kolumn, które zawierają czas w formacie tekstowym typu "HH:MM:SS".
# Te nazwy pasują do pliku "halfmarathon_wroclaw_2024__final.csv" - jeśli
# używasz innego pliku (np. z innego roku), sprawdź `df.columns` i popraw
# tę listę w razie potrzeby.
TIME_COLUMNS = [
    "5 km Czas",
    "10 km Czas",
    "15 km Czas",
    "20 km Czas",
    "Czas",  # to jest czas ukończenia CAŁEGO biegu - przyszły target
]


def time_to_seconds(time_value):
    """
    Zamienia czas zapisany jako tekst ("HH:MM:SS" albo "MM:SS")
    na liczbę sekund (int).

    Przykład:
        "01:45:30" -> 6330
        "25:10"    -> 1510

    Jeśli wartość jest pusta (NaN) albo nie da się jej sparsować,
    funkcja zwraca None - dzięki temu pandas zapisze tam brak danych
    zamiast wywalić błędem.
    """
    # pd.isna sprawdza, czy wartość to "brak danych" (np. pusta komórka w CSV)
    if pd.isna(time_value):
        return None

    # Upewniamy się, że pracujemy na tekście (czasem pandas wczyta to jako liczbę)
    time_str = str(time_value).strip()

    if time_str == "" or time_str.lower() == "nan":
        return None

    # Dzielimy tekst po dwukropku, np. "01:45:30" -> ["01", "45", "30"]
    parts = time_str.split(":")

    try:
        parts = [int(p) for p in parts]  # zamieniamy każdy fragment na liczbę
    except ValueError:
        # Jeśli nie da się zamienić na liczby (np. tekst jest uszkodzony),
        # zwracamy None zamiast wywalić cały skrypt.
        return None

    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        # Nieoczekiwany format - zwracamy brak danych
        return None

    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds


def process_file(input_path: str, output_path: str) -> pd.DataFrame:
    """Wczytuje jeden plik CSV, konwertuje kolumny czasowe i zapisuje wynik."""

    print(f"Wczytuję: {input_path}")
    # sep=None + engine="python" pozwala pandas samemu zgadnąć separator (";" albo ",")
    df = pd.read_csv(input_path, sep=None, engine="python")

    for column in TIME_COLUMNS:
        if column in df.columns:
            # .apply() uruchamia funkcję dla każdej wartości w kolumnie
            df[column + " (s)"] = df[column].apply(time_to_seconds)
        else:
            print(f"  Uwaga: kolumny '{column}' nie znaleziono w pliku, pomijam.")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Zapisano oczyszczony plik: {output_path}\n")
    return df


def main():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

    csv_files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith(".csv")]

    if not csv_files:
        print(f"Nie znaleziono żadnych plików CSV w {RAW_DATA_DIR}")
        print("Wrzuć tam swoje surowe pliki z danymi treningowymi i uruchom skrypt ponownie.")
        return

    for filename in csv_files:
        input_path = os.path.join(RAW_DATA_DIR, filename)
        output_path = os.path.join(PROCESSED_DATA_DIR, filename)
        process_file(input_path, output_path)


# Ten warunek sprawia, że main() uruchomi się tylko wtedy, gdy odpalasz
# ten plik bezpośrednio (python preprocess_time.py), a nie gdy go importujesz.
if __name__ == "__main__":
    main()
