# update_manager.py
import requests
import logging

logger = logging.getLogger(__name__)

VERSION = "3.1"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/MRCHKK/SmartSocialMedia/main/version.json"

def check_for_updates(update_url: str = DEFAULT_UPDATE_URL) -> dict:
    """
    Sprawdza, czy dostępna jest nowsza wersja aplikacji.
    Zwraca słownik z informacjami o aktualizacji, jeśli jest dostępna, w przeciwnym razie None.
    """
    try:
        response = requests.get(update_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            online_version = data.get("version", "")
            download_url = data.get("download_url", "")
            changelog = data.get("changelog", "")
            
            try:
                if float(online_version) > float(VERSION):
                    return {
                        "version": online_version,
                        "download_url": download_url,
                        "changelog": changelog
                    }
            except ValueError:
                if online_version > VERSION:
                    return {
                        "version": online_version,
                        "download_url": download_url,
                        "changelog": changelog
                    }
    except Exception as e:
        logger.warning(f"Błąd podczas sprawdzania aktualizacji: {e}")
    return None
