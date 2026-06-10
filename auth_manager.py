# auth_manager.py
# Zarządza autoryzacją OAuth 2.0 dla Google Business Profile API.
# Przy pierwszym uruchomieniu otwiera przeglądarkę do logowania.
# Następnie token jest zapisywany i automatycznie odświeżany.

import os
import json
import logging

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# Scope wymagany przez Google Business Profile API
SCOPES = ["https://www.googleapis.com/auth/business.manage"]

# Domyślne ścieżki (konfiguracja może je nadpisać)
DEFAULT_SECRETS_FILE = "client_secrets.json"
DEFAULT_TOKEN_FILE = "data/token.json"


def get_credentials(secrets_file: str = None, token_file: str = None) -> Credentials:
    """
    Zwraca ważne poświadczenia OAuth2.
    - Jeśli token.json istnieje i jest ważny — używa go bezpośrednio.
    - Jeśli token wygasł — automatycznie odświeża (refresh_token).
    - Jeśli nie ma tokenu — otwiera przeglądarkę do autoryzacji.

    Args:
        secrets_file: ścieżka do pliku client_secrets.json (z Google Cloud Console)
        token_file: ścieżka gdzie zapisany jest/będzie token.json

    Returns:
        Ważny obiekt Credentials.

    Raises:
        FileNotFoundError: gdy brak pliku client_secrets.json
        Exception: gdy autoryzacja się nie powiedzie
    """
    if secrets_file is None:
        secrets_file = DEFAULT_SECRETS_FILE
    if token_file is None:
        token_file = DEFAULT_TOKEN_FILE

    creds = None

    # 1. Próba wczytania zapisanego tokenu
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            logger.info(f"Wczytano token OAuth2 z: {token_file}")
        except Exception as e:
            logger.warning(f"Nie udało się wczytać tokenu z {token_file}: {e}")
            creds = None

    # 2. Jeśli token wygasł ale mamy refresh_token — odśwież
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Token OAuth2 odświeżony automatycznie.")
            _save_token(creds, token_file)
        except Exception as e:
            logger.warning(f"Nie udało się odświeżyć tokenu: {e}. Wymagana ponowna autoryzacja.")
            creds = None

    # 3. Jeśli nadal brak ważnych credentials — uruchom flow
    if not creds or not creds.valid:
        if not os.path.exists(secrets_file):
            raise FileNotFoundError(
                f"Brak pliku poświadczeń OAuth2: '{secrets_file}'.\n"
                f"Pobierz go z Google Cloud Console → API & Services → Credentials → OAuth 2.0 Client IDs.\n"
                f"Typ aplikacji: 'Desktop app'. Zapisz jako '{secrets_file}' w katalogu projektu."
            )

        logger.info("Uruchamiam przeglądarkę do autoryzacji Google Business Profile...")
        flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
        try:
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
                timeout_seconds=150
            )
        except Exception as e:
            logger.error(f"Błąd uruchamiania lokalnego serwera OAuth: {e}")
            raise Exception("Przekroczono limit czasu autoryzacji (150s) lub anulowano logowanie.") from e

        logger.info("Autoryzacja zakończona pomyślnie.")
        _save_token(creds, token_file)

    return creds


def _save_token(creds: Credentials, token_file: str):
    """Zapisuje token do pliku JSON."""
    try:
        os.makedirs(os.path.dirname(token_file) if os.path.dirname(token_file) else ".", exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        logger.info(f"Token zapisany do: {token_file}")
    except Exception as e:
        logger.error(f"Nie udało się zapisać tokenu: {e}")


def is_authorized(token_file: str = None) -> bool:
    """
    Sprawdza czy istnieje ważny token autoryzacji (bez otwierania przeglądarki).
    
    Returns:
        True jeśli token istnieje i jest ważny (lub da się odświeżyć)
    """
    if token_file is None:
        token_file = DEFAULT_TOKEN_FILE

    if not os.path.exists(token_file):
        return False

    try:
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds, token_file)
            return True
        return False
    except Exception:
        return False


def revoke_authorization(token_file: str = None):
    """Usuwa zapisany token — wymusi ponowną autoryzację przy następnym użyciu."""
    if token_file is None:
        token_file = DEFAULT_TOKEN_FILE

    if os.path.exists(token_file):
        try:
            os.remove(token_file)
            logger.info(f"Token usunięty: {token_file}. Wymagana ponowna autoryzacja.")
        except Exception as e:
            logger.error(f"Nie udało się usunąć tokenu: {e}")


def get_token_info(token_file: str = None) -> dict:
    """
    Zwraca podstawowe informacje o zapisanym tokenie (bez ujawniania sekretów).
    
    Returns:
        Słownik z polami: exists, valid, expired, has_refresh_token
    """
    if token_file is None:
        token_file = DEFAULT_TOKEN_FILE

    info = {
        "exists": False,
        "valid": False,
        "expired": False,
        "has_refresh_token": False
    }

    if not os.path.exists(token_file):
        return info

    info["exists"] = True
    try:
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        info["valid"] = creds.valid
        info["expired"] = creds.expired
        info["has_refresh_token"] = bool(creds.refresh_token)
    except Exception:
        pass

    return info


if __name__ == "__main__":
    # Uruchom bezpośrednio aby przetestować autoryzację
    import sys
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("=== Test autoryzacji Google Business Profile ===")
    try:
        creds = get_credentials()
        print(f"✅ Autoryzacja działa! Token: {creds.token[:20]}...")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Błąd: {e}")
        sys.exit(1)
