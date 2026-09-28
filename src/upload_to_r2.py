"""
upload_to_r2.py

To jest krok 2 tego projektu: wysyłamy oczyszczone dane treningowe
(te, które powstały po uruchomieniu preprocess_time.py) do Cloudflare R2.

Cloudflare R2 to magazyn plików w chmurze - "mówi" tym samym językiem co Amazon S3, dzięki
czemu możemy używać biblioteki boto3 (oficjalne narzędzie do S3), tylko podając inny adres serwera (endpoint).

Uruchomienie:
    python src/upload_to_r2.py
"""

# "os" - do pracy ze ścieżkami plików i zmiennymi środowiskowymi
import os

# Nasze własne funkcje pomocnicze z pliku r2_utils.py (ten sam folder src/)
from r2_management import get_r2_client

# python-dotenv - wczytuje dane logowania z pliku .env, żebyśmy nie musieli wpisywać haseł w kodzie
from dotenv import load_dotenv

load_dotenv()

# Folder, w którym leżą JUŻ OCZYSZCZONE pliki (po przejściu przez
# preprocess_time.py - czyli z dodanymi kolumnami czasu w sekundach).
# os.path.dirname(__file__) to folder, w którym leży TEN plik (src/),
# ".." oznacza "cofnij się o jeden folder wyżej".
PROCESSED_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def upload_folder(local_folder: str, bucket_name: str, prefix: str = "data/"):
    """
    Wysyła WSZYSTKIE pliki CSV z podanego folderu lokalnego do bucketu w R2.

    Parametry:
        local_folder - folder na naszym dysku, z którego bierzemy pliki
        bucket_name  - nazwa bucketu w Cloudflare R2
        prefix       - jakby "podfolder" wewnątrz bucketu, np. "data/",
                        żeby wszystkie dane treningowe trzymać w jednym miejscu
                        (a nie wymieszane z innymi plikami, np. modelami)
    """
    client = get_r2_client()

    # Wybieramy z folderu tylko pliki kończące się na ".csv" - pomijamy
    # np. ukryte pliki systemowe, jeśli jakieś tam są.
    # os.listdir() zwraca listę wszystkich nazw plików/folderów w danym folderze.
    all_files = os.listdir(local_folder)
    csv_files = [filename for filename in all_files if filename.endswith(".csv")]

    # Jeśli nie znaleźliśmy żadnych plików CSV, informujemy o tym użytkownika
    # i kończymy działanie funkcji (return bez wartości).
    if not csv_files:
        print(f"Brak plików CSV w {local_folder} - najpierw uruchom preprocess_time.py")
        return

    # Pętla "for" - dla każdego znalezionego pliku CSV robimy dokładnie
    # to samo: wysyłamy go do R2.
    for filename in csv_files:
        # Ścieżka do pliku NA NASZYM DYSKU (lokalnie)
        local_path = os.path.join(local_folder, filename)

        # "Ścieżka" pliku wewnątrz bucketu R2 - to prefix + nazwa pliku,
        # np. "data/halfmarathon_wroclaw_2024__final.csv"
        remote_key = prefix + filename

        print(f"Wysyłam {local_path} -> r2://{bucket_name}/{remote_key}")

        # upload_file() to metoda z boto3, która robi całą robotę:
        # otwiera plik, czyta go i wysyła do R2.
        client.upload_file(local_path, bucket_name, remote_key)

    print("Wszystkie pliki zostały wysłane do R2.")


def main():
    """
    Funkcja "main" (główna) - to punkt startowy naszego skryptu.
    Trzymanie logiki w osobnej funkcji main() (zamiast pisania wszystkiego
    na "sztywno" w pliku) to dobra praktyka - dzięki temu ten kod można
    też zaimportować z innego pliku i użyć go bez automatycznego odpalania.
    """
    # Nazwę bucketu bierzemy ze zmiennej środowiskowej (z pliku .env),
    # a nie wpisujemy na sztywno - dzięki temu każdy może użyć swojego bucketu.
    bucket_name = os.environ["R2_BUCKET_NAME"]
    upload_folder(PROCESSED_DATA_DIR, bucket_name)


# Ten warunek to bardzo częsty "idiom" w Pythonie. Oznacza:
# "uruchom main() tylko, gdy ten plik jest odpalany bezpośrednio
# (np. komendą `python upload_to_r2.py`), a nie wtedy, gdy ktoś go
# importuje z innego pliku (np. `from upload_to_r2 import upload_folder`)."
if __name__ == "__main__":
    main()
