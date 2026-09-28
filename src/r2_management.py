"""
r2_management.py

Ten plik zawiera funkcje, które łączą się z Cloudflare R2 (magazynem plików w chmurze). 
Napisano je raz, żeby nie kopiować tego samego kodu osobno w notebooku (train_pipeline.ipynb) 
i osobno w aplikacji (streamlit_app.py) - zasada DRY ("Don't Repeat Yourself").
Dzięki temu, jeśli kiedyś zmieni się sposób łączenia się z R2, poprawi się kod tylko w jednym pliku, a nie w kilku.
"""

# Moduł "os" pozwala m.in. odczytywać zmienne środowiskowe i operować na ścieżkach do plików/folderów.
import os

# boto3 to biblioteka Amazona do obsługi usługi S3.
# Cloudflare R2 jest kompatybilne z S3, więc możemy użyć tej samej biblioteki, tylko podając inny adres serwera.
import boto3

from dotenv import load_dotenv
# Wywołujemy load_dotenv() od razu przy imporcie tego pliku, żeby
# zmienne z .env były dostępne zanim użyte zostaną funkcje poniżej.
load_dotenv()

def get_r2_client():
    """
    Tworzy i zwraca "klienta" boto3 - czyli obiekt, przez który wysyłamy
    wszystkie zapytania do Cloudflare R2.

    Dane logowania (klucze) NIE są wpisane na sztywno w kodzie - bierzemy je
    ze zmiennych środowiskowych (os.environ), które pochodzą z pliku .env.
    Dzięki temu nasze prawdziwe hasła nigdy nie trafiają do repozytorium Git.
    """
    return boto3.client(
        service_name="s3",                                          # mówimy boto3, "chcemy rozmawiać w języku S3"
        endpoint_url=os.environ["R2_ENDPOINT_URL"],                 # adres serwera R2
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],           # "login" do R2
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],   # "hasło" do R2
        # WAŻNE!: Cloudflare R2 nie używa prawdziwych regionów jak Amazon, więc zawsze wpisuje się tu stałą wartość: "auto".
        region_name="auto",
    )


def download_file(bucket_name: str, remote_key: str, local_path: str) -> str:
    """
    Pobiera JEDEN plik z bucketu R2 i zapisuje go na dysku lokalnym.

    Parametry:
        bucket_name  - nazwa bucketu w R2
        remote_key   - "ścieżka" pliku wewnątrz bucketu
        local_path   - gdzie na dysku lokalnym zapisać pobrany plik

    Zwraca ścieżkę do pobranego pliku (żeby można było od razu jej użyć,
    np. w pd.read_csv(local_path)).
    """
    client = get_r2_client()

    # Zanim zapiszemy plik, upewniamy się, że folder docelowy istnieje.
    # exist_ok=True oznacza "nie wywalaj błędem, jeśli folder już istnieje".
    folder = os.path.dirname(local_path)
    if folder:  # jeśli local_path to np. samo "plik.csv" (bez folderu), nic nie twórzmy
        os.makedirs(folder, exist_ok=True)

    # Właściwe pobranie pliku z R2 na dysk
    client.download_file(bucket_name, remote_key, local_path)

    return local_path


def upload_file(local_path: str, bucket_name: str, remote_key: str) -> str:
    """
    Wysyła jeden lokalny plik do bucketu.

    Parametry:
        local_path   - ścieżka do pliku na naszym dysku (ten, który jest wysyłany)
        bucket_name  - nazwa bucketu w R2
        remote_key   - pod jaką "ścieżką/nazwą" plik ma się znaleźć w R2

    Zwraca tekstowy adres pliku w stylu "r2://nazwa-bucketu/sciezka" -
    to tylko dla wygody, żeby łatwo wypisać go w konsoli/logach.
    """
    client = get_r2_client()
    client.upload_file(local_path, bucket_name, remote_key)
    return f"r2://{bucket_name}/{remote_key}"


def list_files(bucket_name: str, prefix: str = "") -> list:
    """
    Zwraca listę nazw (kluczy) plików znajdujących się w buckecie R2.

    Parametr "prefix" pozwala zawęzić listę do plików zaczynających się
    od podanego tekstu - np. prefix="data/" zwróci tylko pliki z "folderu"
    data/, a nie wszystkie pliki w całym buckecie.
    """
    client = get_r2_client()

    # list_objects_v2 to metoda z boto3, która pyta R2: "jakie pliki tu masz?"
    response = client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    # Odpowiedź od R2 to skomplikowany słownik (dict). Interesuje nas tylko
    # klucz "Contents" - lista informacji o plikach. Jeśli bucket/folder jest
    # pusty, "Contents" może w ogóle nie istnieć w odpowiedzi - dlatego
    # używamy response.get("Contents", []), czyli "weź Contents, a jeśli go
    # nie ma, użyj pustej listy zamiast wywalać błąd".
    files_info = response.get("Contents", [])

    # List comprehension: dla każdego elementu (obj) w files_info,
    # wyciągamy tylko pole "Key" (czyli samą nazwę/ścieżkę pliku).
    # To to samo co:
    #     wynik = []
    #     for obj in files_info:
    #         wynik.append(obj["Key"])
    return [obj["Key"] for obj in files_info]
