# config_manager.py
import json
import os
import logging

# Konfiguracja logowania do pliku
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    # --- Google Business Profile API (OAuth 2.0) ---
    # Pobierz client_secrets.json z Google Cloud Console:
    # console.cloud.google.com → API & Services → Credentials → OAuth 2.0 Client IDs (typ: Desktop)
    "GBP_CLIENT_SECRETS": "client_secrets.json",
    "GBP_TOKEN_FILE": "data/token.json",

    # Lokalizacje GBP: klucz = "accounts/{accountId}/locations/{locationId}"
    # Można wypełnić automatycznie przez GUI (Ustawienia → Wykryj lokalizacje)
    "LOKALIZACJE": {},

    # --- Ustawienia plików ---
    "CSV_DATABASE": "data/database_opinie.csv",
    "EXCEL_FILE": "raporty/Raport_Opinie.xlsx",

    # --- Powiadomienia ---
    "NOTIFICATIONS_ENABLED": True,

    # --- Klasyfikacja AI ---
    "USE_AI_MODEL": True,  # Możliwość wyłączenia ciężkiego modelu na bardzo słabych komputerach
    # Słownik: "accounts/{accountId}/locations/{locationId}" -> ["Imię Nazwisko 1", "Imię Nazwisko 2"]
    "PRACOWNICY": {},
    "DZIALY": [
        "SERWIS",
        "CZĘŚCI ZAMIENNE",
        "SALON",
        "SAMOCHODY UŻYWANE",
        "UBEZPIECZENIA",
        "BLACHARNIA"
    ],
    "MAPA_DZIALOW": {
        "UBEZPIECZENIA": [
            "oc/ac", "oc", "ac", "polisa", "ubezpieczenie", "ubezpieczenia", "ubezpieczyciel",
            "likwidacja szkód", "szkoda", "szkody", "agent ubezpieczeniowy", "składka", "zniżki",
            "nnw", "gap", "warta", "pzu", "allianz", "ergo hestia", "generali", "franszyza",
            "zielona karta", "wariant serwisowy", "kosztorys szkody"
        ],
        "SERWIS": [
            "serwis", "przegląd", "naprawa", "mechanik", "olej", "wymiana oleju", "klocki",
            "tarcze", "awaria", "usterka", "silnik", "zawieszenie", "diagnosta", "stacja kontroli",
            "robocizna", "gwarancja", "geometria", "klimatyzacja", "odgrzybianie", "kasowanie błędów",
            "serwisant", "warsztat", "filtr oleju", "wymiana kół", "zbieżność"
        ],
        "CZĘŚCI ZAMIENNE": [
            "części zamienne", "części", "akcesoria", "zamiennik", "zamienniki", "filtr",
            "pasek", "świece", "magazyn", "zamówienie części", "opony", "felgi", "wycieraczki",
            "żarówki", "płyny", "oryginalne części", "katalog części", "dział części"
        ],
        "SALON": [
            "salon", "sprzedaż", "zakup", "doradca handlowy", "jazda próbna", "nowe auto",
            "nowy samochód", "konfiguracja", "salon samochodowy", "finansowanie", "leasing",
            "kredyt", "handlowiec", "odbiór auta", "wydanie samochodu", "rabat", "oferta handlowa"
        ],
        "SAMOCHODY UŻYWANE": [
            "samochody używane", "używane", "komis", "odkup", "używka", "stan techniczny",
            "przebieg", "bezwypadkowy", "autohandel", "trade-in", "zamiana", "wycena auta",
            "historia pojazdu", "używany samochód", "dział używanych"
        ],
        "BLACHARNIA": [
            "blacharnia", "blacharstwo", "lakiernia", "lakiernik", "prostowanie", "zarysowanie",
            "wgniecenie", "malowanie", "lakier", "blacha", "szpachla", "elementów",
            "naprawa bezgotówkowa", "auto zastępcze", "spasowanie", "cieniowanie", "zderzak"
        ]
    }
}

# Klucze które zostały usunięte (stare Places API) — ignoruj podczas wczytywania
_DEPRECATED_KEYS = {"API_KEY"}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            loaded = json.load(f)

        # Uzupełnij brakujące klucze domyślnymi wartościami
        for key, default_value in DEFAULT_CONFIG.items():
            if key not in loaded:
                logger.warning(f"Brak klucza '{key}' w konfiguracji — uzupełniam wartością domyślną.")
                loaded[key] = default_value

        # Migracja: stary API_KEY → nowy GBP OAuth
        if "API_KEY" in loaded:
            logger.info("Migracja: klucz 'API_KEY' (Places API) jest przestarzały — używam teraz OAuth2 GBP.")
            # Nie usuwamy go od razu dla kompatybilności, ale nie używamy

        # Migracja: stare Place IDs (ChIJ...) → nowe GBP location names
        # Jeśli LOKALIZACJE jest pusta ale istniały stare ChIJ..., zostawiamy empty (użytkownik skonfiguruje przez GUI)
        if isinstance(loaded.get("LOKALIZACJE"), dict):
            old_style = {k: v for k, v in loaded["LOKALIZACJE"].items() if k.startswith("ChIJ")}
            if old_style:
                logger.warning(
                    f"Wykryto {len(old_style)} lokalizacji w starym formacie Place ID (ChIJ...). "
                    "Wejdź w Ustawienia → 'Wykryj lokalizacje z GBP' żeby pobrać nowe ID."
                )

        # Migracja: stary format PRACOWNICY (lista) -> nowy format (słownik lokalizacja -> lista)
        if isinstance(loaded.get("PRACOWNICY"), list):
            logger.info("Migracja: konwertuję listę pracowników na format per lokalizacja.")
            old_list = loaded["PRACOWNICY"]
            new_dict = {}
            locations = loaded.get("LOKALIZACJE", {})
            if isinstance(locations, dict):
                for loc_id in locations:
                    new_dict[loc_id] = list(old_list)
            new_dict["global"] = list(old_list)
            loaded["PRACOWNICY"] = new_dict

        if isinstance(loaded.get("DZIALY"), dict):
            loaded["DZIALY"] = list(loaded["DZIALY"].keys())

        return loaded
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Błąd odczytu konfiguracji: {e}. Używam ustawień domyślnych.")
        return DEFAULT_CONFIG.copy()


def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)