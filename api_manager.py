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
    # Typowe obcinanie końcówek deklinacyjnych i przymiotnikowych
    if slowo.endswith(("skiego", "ckiego", "skiemu", "ckiemu")):
        return slowo[:-6]
    if slowo.endswith(("skim", "ckim", "skich", "ckich")):
        return slowo[:-4]
    if slowo.endswith(("ski", "cki", "ska", "cka", "ego", "emu", "ych", "ymi")):
        return slowo[:-3]
    if slowo.endswith(("ia", "ie", "io", "ii")):
        return slowo[:-2]
    if slowo.endswith(("a", "u", "y", "e", "o", "i", "m")):
        return slowo[:-1]
    return slowo


import datetime

def _log_review_classification(message: str):
    try:
        os.makedirs("logs", exist_ok=True)
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        log_date_str = now.strftime("%Y-%m-%d")
        log_file = f"logs/review_{log_date_str}.log"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {message}\n")
            
        # Retention: remove review log files older than 7 days
        for filename in os.listdir("logs"):
            if filename.startswith("review_") and filename.endswith(".log"):
                date_part = filename[7:-4] # extracting YYYY-MM-DD
                try:
                    file_date = datetime.datetime.strptime(date_part, "%Y-%m-%d")
                    age = now - file_date
                    if age.days > 7:
                        os.remove(os.path.join("logs", filename))
                except ValueError:
                    pass
    except Exception:
        pass

_review_pipeline = None
_review_model_loaded = False

def get_review_model():
    global _review_pipeline, _review_model_loaded
    if not _review_model_loaded:
        try:
            from transformers import pipeline
            import torch
            
            # Bezpieczny limit wątków CPU dla słabszych procesorów, by nie przeciążać komputera
            if hasattr(torch, "set_num_threads"):
                try:
                    torch.set_num_threads(2)
                except Exception:
                    pass

            model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'model_zero_shot')
            if os.path.exists(model_dir):
                # Ładowanie całkowicie offline z pobranego folderu
                os.environ["HF_HUB_OFFLINE"] = "1"
                _review_pipeline = pipeline("zero-shot-classification", model=model_dir)
            else:
                # Fallback do pobrania (tylko w trybie dev przed zbudowaniem)
                _review_pipeline = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
        except (Exception, MemoryError) as e:
            logger.error(f"Nie udało się zainicjować modelu mDeBERTa-v3-base: {e}")
            _review_pipeline = None
        _review_model_loaded = True
    return _review_pipeline

def _dopasuj_pracownika(tekst: str, pracownicy: list) -> str:
    """Sprawdza dopasowanie pracownika z uwzględnieniem deklinacji i oboczności nazwisk."""
    if not tekst or not pracownicy:
        return None

    tekst_lower = str(tekst).lower()
    tekst_clean = usun_diakrytyki(tekst_lower)
    slowa_tekstu_raw = [w for w in re.findall(r'\w+', tekst_clean) if len(w) >= 3]
    slowa_tekstu_rdzen = [pobierz_rdzen(w) for w in slowa_tekstu_raw]

    # 1. Pełne dopasowanie tekstu z imieniem i nazwiskiem
    for p in pracownicy:
        p_lower = p.lower()
        if p_lower in tekst_lower or usun_diakrytyki(p_lower) in tekst_clean:
            return p

    # 2. Dopasowanie po poszczególnych członach (imię / nazwisko z odmianą)
    for p in pracownicy:
        czlony = p.split()
        for czlon in czlony:
            czlon_clean = usun_diakrytyki(czlon.lower())
            if len(czlon_clean) <= 3:
                continue
            rdzen_czlonu = pobierz_rdzen(czlon_clean)

            # Dokładne dopasowanie rdzeniowe (np. kowalsk == kowalsk, mariusz == mariusz, cielemec == cielemec)
            if rdzen_czlonu in slowa_tekstu_rdzen:
                return p

            # Fuzzy matching dla oboczności (np. Rostka -> Rostek)
            for w_raw, w_rdzen in zip(slowa_tekstu_raw, slowa_tekstu_rdzen):
                if len(w_raw) >= 4 and len(czlon_clean) >= 4:
                    ratio1 = difflib.SequenceMatcher(None, czlon_clean, w_raw).ratio()
                    ratio2 = difflib.SequenceMatcher(None, rdzen_czlonu, w_rdzen).ratio()
                    if ratio1 >= 0.78 or ratio2 >= 0.78:
                        return p
    return None

def _matches_keyword(tekst_lower: str, keyword: str) -> bool:
    """Sprawdza czy słowo kluczowe/pojęcie z mapy myśli występuje w tekście opinii."""
    kw_lower = keyword.lower().strip()
    if not kw_lower:
        return False
    if "/" in kw_lower or "-" in kw_lower or " " in kw_lower:
        return kw_lower in tekst_lower
    
    # Podstawowe sprawdzanie z ograniczeniem słów
    pattern = r'(?<!\w)' + re.escape(kw_lower) + r'(?!\w)'
    if re.search(pattern, tekst_lower):
        return True

    # Sprawdzanie rdzeniowe tylko dla słów o długości >= 4
    if len(kw_lower) >= 4:
        rdzen_kw = pobierz_rdzen(usun_diakrytyki(kw_lower))
        slowa_tekstu = [pobierz_rdzen(usun_diakrytyki(w)) for w in re.findall(r'\w+', tekst_lower) if len(w) >= 4]
        return rdzen_kw in slowa_tekstu
    return False

def przypisz_kategorie(tekst, location_id=None, config=None):
    # Backward compatibility with tests/calls that pass config as the second parameter
    if isinstance(location_id, dict) and config is None:
        config = location_id
        location_id = None

    if config is None:
        config = config_manager.load_config()

    if not tekst or not str(tekst).strip():
        return "Ogólne"

    # Przygotowanie wszystkich dostępnych kategorii z ustawień
    pracownicy_config = config.get("PRACOWNICY", {})
    pracownicy = []
    if isinstance(pracownicy_config, dict):
        if location_id and location_id in pracownicy_config:
            pracownicy.extend(pracownicy_config[location_id])
        if "global" in pracownicy_config:
            for p in pracownicy_config["global"]:
                if p not in pracownicy:
                    pracownicy.append(p)
        if not pracownicy:  # Fallback
            for plist in pracownicy_config.values():
                if isinstance(plist, list):
                    pracownicy.extend(plist)
    elif isinstance(pracownicy_config, list):
        pracownicy = list(pracownicy_config)
    
    dzialy_config = config.get("DZIALY", [])
    dzialy = list(dzialy_config.keys()) if isinstance(dzialy_config, dict) else list(dzialy_config)

    wszystkie_kategorie = list(set(pracownicy + dzialy))

    if not wszystkie_kategorie:
        return "Ogólne"

    tekst_lower = str(tekst).lower()

    # --- KROK 1: SZTYWNE ALGORYTMY (Litera w literę) ---
    # 1. Dokładne dopasowanie imienia/nazwiska pracownika
    dopasowany_pracownik = _dopasuj_pracownika(tekst, pracownicy)
    if dopasowany_pracownik:
        _log_review_classification(f"[Sztywne dopasowanie] Dopasowano pracownika: '{dopasowany_pracownik}'")
        return dopasowany_pracownik

    # 2. Dokładne dopasowanie nazwy działu (litera w literę)
    for d in dzialy:
        d_lower = d.lower()
        if " " in d_lower:
            czlony_d = [pobierz_rdzen(usun_diakrytyki(w)) for w in d_lower.split() if len(w) >= 3]
            slowa_t = [pobierz_rdzen(usun_diakrytyki(w)) for w in re.findall(r'\w+', tekst_lower)]
            if czlony_d and all(c in slowa_t for c in czlony_d):
                _log_review_classification(f"[Sztywne dopasowanie] Dopasowano wielowyrazowy dział: '{d}'")
                return d
        else:
            if _matches_keyword(tekst_lower, d_lower):
                _log_review_classification(f"[Sztywne dopasowanie] Dopasowano nazwę działu: '{d}'")
                return d

    # --- KROK 2: MAPA MYŚLI (Pojęcia i Słowa Kluczowe Działów) ---
    mapa_dzialow = config.get("MAPA_DZIALOW", {})
    if isinstance(mapa_dzialow, dict):
        znalezione_z_mapy = []
        for dzial_nazwa, slowa_kluczowe in mapa_dzialow.items():
            if dzialy and dzial_nazwa.upper() not in [d.upper() for d in dzialy]:
                continue
            for kw in slowa_kluczowe:
                if _matches_keyword(tekst_lower, kw):
                    znalezione_z_mapy.append((dzial_nazwa, kw))
        
        if znalezione_z_mapy:
            znalezione_z_mapy.sort(key=lambda x: len(x[1]), reverse=True)
            wygrywajacy_dzial, pasujace_slowo = znalezione_z_mapy[0]
            oryg_dzial = next((d for d in dzialy if d.upper() == wygrywajacy_dzial.upper()), wygrywajacy_dzial)
            _log_review_classification(f"[Mapa Myśli] Dopasowano dział '{oryg_dzial}' na podstawie pojęcia: '{pasujace_slowo}'")
            return oryg_dzial

    # --- KROK 3: SZTUCZNA INTELIGENCJA AI (mDeBERTa-v3 dla nietypowych opinii) ---
    use_ai = config.get("USE_AI_MODEL", True)
    if not use_ai:
        _log_review_classification("[Konfiguracja] Model AI wyłączony w ustawieniach. Zwracam 'Ogólne'.")
        return "Ogólne"

    classifier = get_review_model()
    if classifier is not None:
        try:
            # Mapowanie nazw kategorii na pełniejsze opisy kontekstowe dla modelu AI
            opis_kategorii_map = {
                "serwis": "usługi naprawcze, mechanik, przegląd techniczny, usterka lub serwis samochodu",
                "części zamienne": "zamawianie części, sprzedaż elementów, akcesoria, czujniki, vin lub części zamienne",
                "salon": "zakup nowego samochodu, salon sprzedaży, jazda próbna lub doradztwo handlowe",
                "samochody używane": "zakup lub odkup używanego samochodu, komis lub auto używane",
                "ubezpieczenia": "polisa ubezpieczeniowa, OC/AC, zniżki lub formalności ubezpieczeniowe",
                "blacharnia": "naprawa blacharsko-lakiernicza, lakierowanie, usuwanie wgnieceń lub szkoda lakiernicza"
            }

            candidate_labels = []
            label_to_kategoria = {}

            for k in wszystkie_kategorie:
                k_low = k.lower()
                opis = opis_kategorii_map.get(k_low, f"dział lub pracownik {k}")
                candidate_labels.append(opis)
                label_to_kategoria[opis] = k

            neutral_label = "inny ogólny temat / opinia bez odniesienia do konkretnego działu"
            candidate_labels.append(neutral_label)

            result = classifier(
                tekst,
                candidate_labels=candidate_labels,
                multi_label=False,
                hypothesis_template="W tej recenzji Google klient salonu/serwisu samochodowego porusza temat dotyczący: {}."
            )
            najlepsza_kategoria_low = result["labels"][0]
            pewnosc = result["scores"][0]

            if najlepsza_kategoria_low == neutral_label:
                _log_review_classification(f"[Zero-Shot AI] Wykryto brak konkretnego działu ({neutral_label}). Zwracam 'Ogólne'.")
                return "Ogólne"

            najlepsza_kategoria = label_to_kategoria.get(najlepsza_kategoria_low, "Ogólne")
            najlepsza_low = najlepsza_kategoria.lower()

            if "samochody używane" in najlepsza_low or "używane" in najlepsza_low:
                slowa_t = [pobierz_rdzen(usun_diakrytyki(w)) for w in re.findall(r'\w+', tekst_lower)]
                has_auto = any(w in slowa_t for w in ["samochod", "auto", "pojazd", "woz"])
                has_uzywane = any(w in slowa_t for w in ["uzywan", "uzywka", "komis", "odkup", "trade", "bezwypadkow", "przebieg"])
                if not (has_auto and has_uzywane):
                    _log_review_classification(f"[Zero-Shot AI] Odrzucono '{najlepsza_kategoria}' - brak wymaganych obu członów (samochód + używany).")
                    return "Ogólne"

            # Obniżony próg dla wzbogaconego kontekstowo promptu
            if pewnosc >= 0.70:
                _log_review_classification(f"[Zero-Shot AI mDeBERTa] AI dopasowało '{najlepsza_kategoria}' na podstawie kontekstu opinii (pewność: {pewnosc:.2f})")
                return najlepsza_kategoria
            else:
                _log_review_classification(f"[Zero-Shot AI mDeBERTa] Odrzucono '{najlepsza_kategoria}' (pewność {pewnosc:.2f} < 0.70). Zwracam 'Ogólne'.")
        except Exception as e:
            logger.exception("Błąd podczas klasyfikacji modelem AI. Zwracam 'Ogólne'.")
            
    return "Ogólne"



def wczytaj_istniejace_opinie(csv_path):
    """Wczytuje istniejące opinie z CSV i zwraca słownik {klucz: wiersz}."""
    istniejace = {}
    if not os.path.exists(csv_path):
        logger.info(f"Plik bazy CSV nie istnieje pod ścieżką: {csv_path}")
        return istniejace
    try:
        with open(csv_path, mode='r', encoding='utf-8', errors='replace', newline='') as file:
            reader = csv.DictReader(file)
            line_idx = 1
            for row in reader:
                line_idx += 1
                if not isinstance(row, dict):
                    logger.warning(f"Linia {line_idx} w pliku CSV ma niepoprawną strukturę i została pominięta.")
                    continue
                
                review_id = (row.get('ReviewID') or '').strip()
                if review_id:
                    istniejace[review_id] = row
                else:
                    autor = row.get('Autor', '')
                    data = row.get('Data', '')
                    lokalizacja = row.get('Lokalizacja', '')
                    if autor or data or lokalizacja:
                        klucz_kompozytowy = f"{autor}_{data}_{lokalizacja}"
                        row['ReviewID'] = klucz_kompozytowy
                        istniejace[klucz_kompozytowy] = row
                        logger.debug(f"Linia {line_idx}: Brak pola ReviewID. Utworzono klucz kompozytowy: {klucz_kompozytowy}")
                    else:
                        logger.warning(f"Linia {line_idx} w pliku CSV nie zawiera danych opinii. Pomijam.")
        logger.info(f"Pomyślnie wczytano {len(istniejace)} opinii z pliku CSV: {csv_path}")
    except Exception as e:
        logger.error(f"Nie udało się wczytać istniejących opinii z {csv_path}: {e}", exc_info=True)
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
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in istniejace.values():
            writer.writerow({col: row.get(col, '') for col in fieldnames})

    logger.info(f"Reklasyfikacja zakończona. Zaktualizowano {zaktualizowane_count} opinii w bazie.")
    return zaktualizowane_count