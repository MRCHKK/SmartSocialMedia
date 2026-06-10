# api_manager.py
# Obsługuje pobieranie recenzji z Google Business Profile API (OAuth 2.0).
# Zastępuje stare Google Places API (limit 5 recenzji) — brak limitu recenzji.

import requests
import csv
import re
import os
import shutil
import logging
import threading
import difflib
from dateutil import parser, tz

try:
    from plyer import notification
except ImportError:
    notification = None

import config_manager
import auth_manager

logger = logging.getLogger(__name__)

# Endpointy Google Business Profile API
GBP_ACCOUNT_MANAGEMENT_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
GBP_BUSINESS_INFO_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
GBP_REVIEWS_URL = "https://mybusiness.googleapis.com/v4"


def _get_auth_headers() -> dict:
    """
    Buduje nagłówki HTTP z aktualnym tokenem OAuth2.
    Token jest automatycznie odświeżany jeśli wygasł.
    """
    config = config_manager.load_config()
    secrets_file = config.get("GBP_CLIENT_SECRETS", "client_secrets.json")
    token_file = config.get("GBP_TOKEN_FILE", "data/token.json")

    creds = auth_manager.get_credentials(secrets_file, token_file)

    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _log_http_call(method: str, url: str, headers: dict, params: dict = None, response = None) -> None:
    safe_headers = {k: ("Bearer ***" if k.lower() == "authorization" else v) for k, v in headers.items()}
    msg = f"HTTP Request: {method} {url}"
    if params:
        msg += f" | Params: {params}"
    msg += f" | Headers: {safe_headers}"
    logger.info(msg)
    if response is not None:
        body_str = response.text
        if len(body_str) > 3000:
            body_str = body_str[:3000] + "... [TRUNCATED]"
        logger.info(f"HTTP Response Status: {response.status_code} | Body: {body_str}")


def formatuj_czas_warszawa(czas_z_api):
    if not czas_z_api:
        return ""
    try:
        dt = parser.parse(czas_z_api)
        dt_polska = dt.astimezone(tz.gettz('Europe/Warsaw'))
        return dt_polska.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return czas_z_api


def usun_diakrytyki(s: str) -> str:
    if not s:
        return ""
    polskie = "ąęćłńóśźżĄĘĆŁŃÓŚŹŻ"
    lacina  = "aeclnoszzAECLNOSZZ"
    tabela = str.maketrans(polskie, lacina)
    return s.translate(tabela)


def pobierz_rdzen(slowo: str) -> str:
    slowo = usun_diakrytyki(slowo.lower().strip())
    if len(slowo) <= 3:
        return slowo
    # Końcówki przymiotnikowe/nazwiskowe -ski, -cki, -ska, -cka
    if slowo.endswith(("skiego", "ckiego", "skiemu", "ckiemu")):
        slowo = slowo[:-6]
    elif slowo.endswith(("ski", "cki", "ska", "cka")):
        slowo = slowo[:-3]
    elif slowo.endswith(("skim", "ckim", "skich", "ckich")):
        slowo = slowo[:-4]

    # Typowe obcinanie końcówek deklinacyjnych
    if slowo.endswith(("ia", "ie", "io", "ii", "ia")):
        return slowo[:-2]
    if slowo.endswith(("a", "u", "y", "e", "o", "i", "m")):
        return slowo[:-1]
    return slowo


def przypisz_kategorie(tekst, location_id=None, config=None):
    # Backward compatibility with tests/calls that pass config as the second parameter
    if isinstance(location_id, dict) and config is None:
        config = location_id
        location_id = None

    if config is None:
        config = config_manager.load_config()

    if not tekst:
        return "Ogólne"

    # Rozbijamy tekst opinii na słowa i oczyszczamy je z diakrytyków
    slowa_surowe = re.findall(r'\b\w+\b', tekst.lower())
    if not slowa_surowe:
        return "Ogólne"

    slowa_norm = [usun_diakrytyki(w) for w in slowa_surowe]
    slowa_rdzenie = [pobierz_rdzen(w) for w in slowa_surowe]

    # PRIORYTET 1 (Pracownicy - czysta lista per lokalizacja)
    pracownicy_config = config.get("PRACOWNICY", {})
    pracownicy = []
    
    if isinstance(pracownicy_config, dict):
        if location_id and location_id in pracownicy_config:
            pracownicy = list(pracownicy_config[location_id])
            # Dołącz pracowników globalnych do puli dopasowania dla tej lokalizacji
            if "global" in pracownicy_config:
                for p in pracownicy_config["global"]:
                    if p not in pracownicy:
                        pracownicy.append(p)
        elif "global" in pracownicy_config:
            pracownicy = pracownicy_config["global"]
        else:
            # Fallback — połącz wszystkich pracowników z różnych lokalizacji
            for plist in pracownicy_config.values():
                if isinstance(plist, list):
                    pracownicy.extend(plist)
            pracownicy = list(set(pracownicy))
    elif isinstance(pracownicy_config, list):
        pracownicy = pracownicy_config

    for pracownik in pracownicy:
        czlony = pracownik.lower().split()
        for czlon in czlony:
            if len(czlon) > 2:
                czlon_norm = usun_diakrytyki(czlon)
                czlon_rdzen = pobierz_rdzen(czlon)

                # 1. Krok: Dopasowanie rdzeniowe / podciągu (bardzo precyzyjne)
                dopasowanie_rdzen = False
                for w_norm, w_rdzen in zip(slowa_norm, slowa_rdzenie):
                    # Jeśli rdzeń imienia/nazwiska pasuje do rdzenia słowa w opinii
                    if czlon_rdzen == w_rdzen or w_norm.startswith(czlon_rdzen):
                        dopasowanie_rdzen = True
                        break
                
                if dopasowanie_rdzen:
                    return pracownik

                # 2. Krok: Fuzzy fallback
                matches = difflib.get_close_matches(czlon_norm, slowa_norm, n=1, cutoff=0.68)
                if matches:
                    return pracownik

    # PRIORYTET 2 (Działy - czysta lista)
    dzialy = config.get("DZIALY", [])
    if isinstance(dzialy, dict):
        dzialy = list(dzialy.keys())

    for dzial in dzialy:
        # Obsługa aliasów zdefiniowanych jako wartości w dict (jeśli config ma taką strukturę)
        dzialy_config = config.get("DZIALY", {})
        synonimy = []
        if isinstance(dzialy_config, dict):
            synonimy = dzialy_config.get(dzial, [])
            if isinstance(synonimy, str):
                synonimy = [synonimy]

        # Szukamy zarówno po pełnej nazwie działu, jak i po jego członach / aliasach
        wyszukiwane_frazy = [dzial] + synonimy
        for fraza in wyszukiwane_frazy:
            czlony = fraza.lower().split()
            for czlon in czlony:
                if len(czlon) > 2:
                    czlon_norm = usun_diakrytyki(czlon)
                    czlon_rdzen = pobierz_rdzen(czlon)

                    dopasowanie_rdzen = False
                    for w_norm, w_rdzen in zip(slowa_norm, slowa_rdzenie):
                        if czlon_rdzen == w_rdzen or w_norm.startswith(czlon_rdzen):
                            dopasowanie_rdzen = True
                            break
                    
                    if dopasowanie_rdzen:
                        return dzial

                    matches = difflib.get_close_matches(czlon_norm, slowa_norm, n=1, cutoff=0.68)
                    if matches:
                        return dzial

    return "Ogólne"


def wczytaj_istniejace_opinie(csv_path):
    """Wczytuje istniejące opinie z CSV i zwraca słownik {klucz: wiersz}."""
    istniejace = {}
    if not os.path.exists(csv_path):
        return istniejace
    try:
        with open(csv_path, mode='r', encoding='utf-8', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                review_id = row.get('ReviewID', '').strip()
                if review_id:
                    istniejace[review_id] = row
                else:
                    # Fallback dla starego formatu CSV
                    klucz_kompozytowy = f"{row.get('Autor', '')}_{row.get('Data', '')}_{row.get('Lokalizacja', '')}"
                    row['ReviewID'] = ''
                    istniejace[klucz_kompozytowy] = row
    except Exception as e:
        logger.warning(f"Nie udało się wczytać istniejących opinii: {e}")
    return istniejace


def trigger_notification(tytul, tresc):
    if not notification:
        return
    def show():
        try:
            notification.notify(
                title=tytul,
                message=tresc,
                app_name="SmartSocialMedia",
                timeout=10
            )
        except Exception as e:
            logger.error(f"Nie udało się wyświetlić powiadomienia na ekranie: {e}")
    threading.Thread(target=show, daemon=True).start()


def pobierz_konta_i_lokalizacje() -> list:
    """
    Pobiera listę kont Google Business Profile i ich lokalizacji.
    
    Returns:
        Lista słowników: [{"name": "accounts/X/locations/Y", "title": "Nazwa firmy"}, ...]
    """
    try:
        headers = _get_auth_headers()
    except FileNotFoundError as e:
        logger.error(f"Brak pliku client_secrets.json: {e}")
        raise
    except Exception as e:
        logger.error(f"Błąd autoryzacji: {e}")
        raise

    wszystkie_lokalizacje = []

    # 1. Pobierz listę kont
    try:
        response = requests.get(GBP_ACCOUNT_MANAGEMENT_URL, headers=headers)
        _log_http_call("GET", GBP_ACCOUNT_MANAGEMENT_URL, headers, response=response)
        response.raise_for_status()
        accounts_data = response.json()
    except Exception as e:
        logger.error(f"Błąd pobierania kont GBP: {e}")
        raise

    accounts = accounts_data.get("accounts", [])
    if not accounts:
        logger.warning("Nie znaleziono żadnych kont Google Business Profile.")
        return []

    logger.info(f"Znaleziono {len(accounts)} kont(o) GBP.")

    # 2. Dla każdego konta pobierz lokalizacje
    for account in accounts:
        account_name = account.get("name", "")  # np. "accounts/123456789"
        if not account_name:
            continue

        loc_url = f"{GBP_BUSINESS_INFO_URL}/{account_name}/locations"
        params = {
            "readMask": "name,title,metadata",
            "pageSize": 100
        }

        next_page_token = None
        while True:
            if next_page_token:
                params["pageToken"] = next_page_token

            try:
                resp = requests.get(loc_url, headers=headers, params=params)
                _log_http_call("GET", loc_url, headers, params=params, response=resp)
                resp.raise_for_status()
                loc_data = resp.json()
            except Exception as e:
                logger.error(f"Błąd pobierania lokalizacji dla konta {account_name}: {e}")
                break

            for loc in loc_data.get("locations", []):
                raw_name = loc.get("name", "")
                # Business Information v1 API returns "locations/{locationId}".
                # To query reviews via v4, we need "accounts/{accountId}/locations/{locationId}".
                if raw_name.startswith("locations/"):
                    location_id = raw_name.split("/")[-1]
                    full_name = f"{account_name}/locations/{location_id}"
                else:
                    full_name = raw_name
                wszystkie_lokalizacje.append({
                    "name": full_name,
                    "title": loc.get("title", "Bez nazwy"),
                })

            next_page_token = loc_data.get("nextPageToken")
            if not next_page_token:
                break

    logger.info(f"Łącznie znaleziono {len(wszystkie_lokalizacje)} lokalizacji GBP.")
    return wszystkie_lokalizacje


def _pobierz_recenzje_lokalizacji(location_name: str, headers: dict) -> list:
    """
    Pobiera WSZYSTKIE recenzje dla danej lokalizacji (z paginacją).
    
    Args:
        location_name: np. "accounts/123/locations/456"
        headers: nagłówki z tokenem OAuth2
    
    Returns:
        Lista recenzji z API
    """
    if not location_name.startswith("accounts/"):
        logger.error(
            f"Lokalizacja '{location_name}' ma niepoprawny format! "
            f"API recenzji (v4) wymaga formatu 'accounts/{{accountId}}/locations/{{locationId}}'. "
            f"Pobieranie recenzji dla tej lokalizacji prawdopodobnie zwróci błąd 404."
        )

    all_reviews = []
    url = f"{GBP_REVIEWS_URL}/{location_name}/reviews"
    params = {"pageSize": 50}
    next_page_token = None
    page = 1

    while True:
        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            response = requests.get(url, headers=headers, params=params)
            _log_http_call("GET", url, headers, params=params, response=response)
            if response.status_code == 200:
                data = response.json()
                reviews = data.get("reviews", [])
                all_reviews.extend(reviews)
                logger.debug(f"  Strona {page}: pobrano {len(reviews)} recenzji.")
                next_page_token = data.get("nextPageToken")
                page += 1
                if not next_page_token:
                    break
            else:
                logger.error(f"Błąd API recenzji ({location_name}): {response.status_code} — {response.text[:300]}")
                break
        except Exception as e:
            logger.exception(f"Błąd techniczny przy pobieraniu recenzji ({location_name})")
            break

    return all_reviews


def mapuj_recenzje(r: dict, z_lokalizacji: str, location_id: str = None, config: dict = None) -> dict:
    """
    Mapuje surowy słownik recenzji z Google Business Profile API do formatu bazodanowego.
    """
    review_id = r.get("reviewId") or r.get("name") or ""
    
    # Bezpieczne pobieranie autora (obsługa None dla reviewer)
    reviewer = r.get("reviewer")
    author = "Anonim"
    if isinstance(reviewer, dict):
        author = reviewer.get("displayName") or "Anonim"

    rating_str = r.get("starRating", "ZERO")
    lokalizacja = r.get('z_lokalizacji') or z_lokalizacji or 'Nieznana'

    # Zabezpieczenie przed typem ratingu (słowny vs numeryczny)
    if isinstance(rating_str, int):
        rating = rating_str
    elif isinstance(rating_str, str) and rating_str.isdigit():
        rating = int(rating_str)
    else:
        rating_map = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "ZERO": 0}
        rating = rating_map.get(str(rating_str).upper(), 0)

    # Treść recenzji
    text = r.get("comment") or ""

    # Data
    surowa_data = r.get("createTime") or r.get("updateTime") or ""
    date = formatuj_czas_warszawa(surowa_data)

    kategoria = przypisz_kategorie(text, location_id, config)

    return {
        'Lokalizacja': lokalizacja,
        'Autor': author,
        'Ocena': rating,
        'Data': date,
        'Kategoria': kategoria,
        'Tresc': text,
        'ReviewID': review_id
    }


def pobierz_z_google():
    """
    Główna funkcja pobierania recenzji z Google Business Profile API.
    Zastępuje stare Places API — brak limitu recenzji, pełna paginacja.
    """
    config = config_manager.load_config()
    wszystkie_opinie = []

    lokalizacje = config.get("LOKALIZACJE", {})
    if not lokalizacje:
        print("Brak skonfigurowanych lokalizacji. Przejdź do Ustawień i skonfiguruj lokalizacje.")
        logger.warning("Brak lokalizacji w konfiguracji.")
        return

    print(f"\n[1] Rozpoczynam pobieranie z {len(lokalizacje)} lokalizacji (Google Business Profile API)...")
    logger.info(f"Rozpoczynam pobieranie GBP z {len(lokalizacje)} lokalizacji")

    try:
        headers = _get_auth_headers()
    except FileNotFoundError as e:
        print(f"\n❌ BŁĄD AUTORYZACJI: {e}")
        logger.error(f"Brak pliku client_secrets.json: {e}")
        return
    except Exception as e:
        print(f"\n❌ BŁĄD AUTORYZACJI: {e}")
        logger.error(f"Błąd autoryzacji OAuth2: {e}")
        return

    for idx, (location_name, nazwa_lokalizacji) in enumerate(lokalizacje.items(), 1):
        print(f" -> Łączenie z lokalizacją {idx}/{len(lokalizacje)} ({nazwa_lokalizacji})...")

        reviews = _pobierz_recenzje_lokalizacji(location_name, headers)
        logger.info(f"Pobrano {len(reviews)} recenzji z '{nazwa_lokalizacji}'")
        print(f"    ✓ Pobrano {len(reviews)} recenzji")

        for r in reviews:
            r['z_lokalizacji'] = nazwa_lokalizacji
            r['location_id'] = location_name
            wszystkie_opinie.append(r)

    if not wszystkie_opinie:
        print("Nie pobrano żadnych opinii ze wskazanych lokalizacji.")
        return

    csv_path = config["CSV_DATABASE"]

    # Tworzenie bezpiecznego katalogu
    if os.path.dirname(csv_path):
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    # Backup starego pliku
    if os.path.exists(csv_path):
        backup_path = csv_path + ".bak"
        shutil.copy2(csv_path, backup_path)
        print(f"  Backup bazy: {backup_path}")

    # Wczytaj istniejące dla deduplikacji
    istniejace = wczytaj_istniejace_opinie(csv_path)

    nowe_opinie = {}
    nowe_dla_powiadomien = []
    alerts_enabled = config.get("NOTIFICATIONS_ENABLED", True)

    for r in wszystkie_opinie:
        mapped = mapuj_recenzje(r, r.get('z_lokalizacji', 'Nieznana'), r.get('location_id'), config)
        review_id = mapped['ReviewID']
        author = mapped['Autor']
        rating = mapped['Ocena']
        lokalizacja = mapped['Lokalizacja']
        
        nowe_opinie[review_id] = mapped

        # Sprawdzenie alertu negatywnej opinii
        if review_id not in istniejace and rating <= 3 and rating > 0:
            nowe_dla_powiadomien.append({
                **r,
                "_author": author,
                "_rating": rating,
                "_lokalizacja": lokalizacja
            })

    # Wysłanie toastów powiadomień
    if alerts_enabled and nowe_dla_powiadomien:
        for nr in nowe_dla_powiadomien:
            author = nr.get("_author", "Anonim")
            rating = nr.get("_rating", 0)
            lok = nr.get("_lokalizacja", "")
            tytul = "🚨 Świeża krytyczna opinia!"
            msg = f"{author} wystawił {rating}⭐ dla lokacji: {lok}."
            trigger_notification(tytul, msg)
            logger.info(f"Wysyłam alarm o niskiej ocenie GBP ({rating}*) -> {author}")

    nowe_count = sum(1 for rid in nowe_opinie if rid not in istniejace)
    merged = {**istniejace, **nowe_opinie}

    fieldnames = ['Lokalizacja', 'Autor', 'Ocena', 'Data', 'Kategoria', 'Tresc', 'ReviewID']
    with open(csv_path, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in merged.values():
            writer.writerow(row)

    print(f"\n✅ Sukces! Zebrano {len(wszystkie_opinie)} opinii z GBP API ({nowe_count} nowych). Łącznie w bazie: {len(merged)}.")


def pobierz_szczegoly_lokalizacji() -> list:
    """
    Pobiera szczegóły (nazwa, ocena, liczba recenzji) skonfigurowanych lokalizacji.
    Używa Business Information API.
    
    Returns:
        Lista słowników z polami: place_id, custom_name, display_name, rating, userRatingCount
    """
    config = config_manager.load_config()
    szczegoly = []

    lokalizacje = config.get("LOKALIZACJE", {})
    if not lokalizacje:
        return szczegoly

    try:
        headers = _get_auth_headers()
    except Exception as e:
        logger.error(f"Błąd autoryzacji przy pobieraniu szczegółów: {e}")
        # Fallback — zwróć dane z konfiguracji bez danych z API
        for location_name, nazwa_lokalizacji in lokalizacje.items():
            szczegoly.append({
                "place_id": location_name,
                "custom_name": nazwa_lokalizacji,
                "display_name": nazwa_lokalizacji,
                "rating": "Brak autoryzacji",
                "userRatingCount": "-"
            })
        return szczegoly

    for location_name, nazwa_lokalizacji in lokalizacje.items():
        # The v1 Business Information API expects "locations/{locationId}".
        # If config contains the full v4 path "accounts/{accountId}/locations/{locationId}",
        # we strip out the account prefix to avoid 404.
        clean_location_name = location_name
        if "locations/" in location_name:
            idx = location_name.find("locations/")
            clean_location_name = location_name[idx:]
            
        url = f"{GBP_BUSINESS_INFO_URL}/{clean_location_name}"
        params = {"readMask": "name,title,metadata"}

        try:
            response = requests.get(url, headers=headers, params=params)
            _log_http_call("GET", url, headers, params=params, response=response)
            if response.status_code == 200:
                data = response.json()
                display_name = data.get("title", nazwa_lokalizacji)
                metadata = data.get("metadata", {})
                # Ocena i liczba recenzji są w metadata dla nowszego API
                # Fallback na mapsUri jeśli brak bezpośrednich pól
                rating = metadata.get("averageRating", data.get("averageRating", "—"))
                count = metadata.get("totalReviewCount", data.get("totalReviewCount", "—"))

                szczegoly.append({
                    "place_id": location_name,
                    "custom_name": nazwa_lokalizacji,
                    "display_name": display_name,
                    "rating": rating,
                    "userRatingCount": count
                })
            else:
                logger.error(f"Błąd API szczegóły dla '{nazwa_lokalizacji}': {response.status_code} — {response.text[:200]}")
                szczegoly.append({
                    "place_id": location_name,
                    "custom_name": nazwa_lokalizacji,
                    "display_name": nazwa_lokalizacji,
                    "rating": "Błąd API",
                    "userRatingCount": "-"
                })
        except Exception as e:
            logger.exception(f"Błąd techniczny przy '{nazwa_lokalizacji}'")
            szczegoly.append({
                "place_id": location_name,
                "custom_name": nazwa_lokalizacji,
                "display_name": nazwa_lokalizacji,
                "rating": "Błąd",
                "userRatingCount": "-"
            })

    return szczegoly


def reklasyfikuj_baze_csv() -> int:
    """
    Przechodzi przez wszystkie opinie zapisane w bazie CSV i na nowo
    przypisuje im kategorie na podstawie aktualnej konfiguracji pracowników i działów.
    Zwraca liczbę zaktualizowanych opinii.
    """
    config = config_manager.load_config()
    csv_path = config.get("CSV_DATABASE", "data/database_opinie.csv")
    if not os.path.exists(csv_path):
        return 0
        
    istniejace = wczytaj_istniejace_opinie(csv_path)
    if not istniejace:
        return 0

    zaktualizowane_count = 0
    lokalizacje = config.get("LOKALIZACJE", {})
    display_to_id = {v: k for k, v in lokalizacje.items()}

    for review_id, row in istniejace.items():
        stara_kat = row.get("Kategoria", "Ogólne")
        loc_display = row.get("Lokalizacja", "")
        location_id = display_to_id.get(loc_display)
        nowa_kat = przypisz_kategorie(row.get("Tresc", ""), location_id, config)
        if stara_kat != nowa_kat:
            row["Kategoria"] = nowa_kat
            zaktualizowane_count += 1

    # Zapisz z powrotem do CSV
    fieldnames = ['Lokalizacja', 'Autor', 'Ocena', 'Data', 'Kategoria', 'Tresc', 'ReviewID']
    with open(csv_path, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in istniejace.values():
            writer.writerow(row)

    logger.info(f"Reklasyfikacja zakończona. Zaktualizowano {zaktualizowane_count} opinii w bazie.")
    return zaktualizowane_count