# tests.py — Testy jednostkowe dla kluczowych funkcji
import unittest
import unittest.mock
import os
import json

import config_manager
import update_manager
from api_manager import formatuj_czas_warszawa, przypisz_kategorie


class TestFormatujCzasWarszawa(unittest.TestCase):
    """Testy konwersji czasu UTC → czas warszawski."""

    def test_prawidlowy_czas_utc_zima(self):
        # UTC+1 zimą → 16:22 UTC = 17:22 CET
        result = formatuj_czas_warszawa("2026-02-17T16:22:00Z")
        self.assertEqual(result, "17.02.2026 17:22")

    def test_prawidlowy_czas_utc_lato(self):
        # UTC+2 latem (CEST) → 14:00 UTC = 16:00 CEST
        result = formatuj_czas_warszawa("2026-06-15T14:00:00Z")
        self.assertEqual(result, "15.06.2026 16:00")

    def test_pusty_string(self):
        self.assertEqual(formatuj_czas_warszawa(""), "")

    def test_none(self):
        self.assertEqual(formatuj_czas_warszawa(None), "")

    def test_nieprawidlowy_format_zwraca_oryginal(self):
        result = formatuj_czas_warszawa("nie-data")
        self.assertIsInstance(result, str)


class TestPrzypisKategorie(unittest.TestCase):
    """Testy przypisywania kategorii na podstawie słów kluczowych."""

    def setUp(self):
        self.config = {
            "PRACOWNICY": {
                "accounts/123/locations/test_loc_3": [
                    "Jan Kowalski",
                    "Kamil Malinowski"
                ],
                "accounts/123/locations/test_loc_4": [
                    "Anna Nowak",
                    "Piotr Wiśniewski"
                ],
                "global": [
                    "Mariusz Cudny"
                ]
            },
            "DZIALY": [
                "Serwis",
                "Dział handlu"
            ]
        }

    def test_rozpoznaje_pracownika_dla_konkretnej_lokalizacji(self):
        # Jan Kowalski pracuje w test_loc_3
        self.assertEqual(
            przypisz_kategorie("Bardzo polecam Pana Kowalskiego!", "accounts/123/locations/test_loc_3", self.config),
            "Jan Kowalski"
        )
        # Anna Nowak pracuje w test_loc_4, nie powinna zostać dopasowana dla test_loc_3
        self.assertEqual(
            przypisz_kategorie("Bardzo polecam panią Annę Nowak!", "accounts/123/locations/test_loc_3", self.config),
            "Ogólne"
        )

    def test_rozpoznaje_pracownika_globalnego(self):
        # Mariusz Cudny jest pracownikiem globalnym
        self.assertEqual(
            przypisz_kategorie("Świetny kontakt z panem Mariuszem!", "accounts/123/locations/test_loc_3", self.config),
            "Mariusz Cudny"
        )

    def test_rozpoznaje_dzial(self):
        self.assertEqual(
            przypisz_kategorie("Serwis na najwyższym poziomie", "accounts/123/locations/test_loc_3", self.config),
            "Serwis"
        )

    def test_pracownik_ma_priorytet_nad_dzialem(self):
        self.assertEqual(
            przypisz_kategorie("Pan Kowalski z serwisu był świetny", "accounts/123/locations/test_loc_3", self.config),
            "Jan Kowalski"
        )

    def test_brak_kategorii_zwraca_ogolne(self):
        self.assertEqual(
            przypisz_kategorie("Fajne miejsce, polecam", "accounts/123/locations/test_loc_3", self.config),
            "Ogólne"
        )

    def test_pusty_tekst(self):
        self.assertEqual(przypisz_kategorie("", "accounts/123/locations/test_loc_3", self.config), "Ogólne")

    def test_none_tekst(self):
        self.assertEqual(przypisz_kategorie(None, "accounts/123/locations/test_loc_3", self.config), "Ogólne")

    def test_case_insensitive(self):
        self.assertEqual(
            przypisz_kategorie("SERWIS BYŁ ŚWIETNY", "accounts/123/locations/test_loc_3", self.config),
            "Serwis"
        )

    def test_polskie_znaki_i_braki(self):
        # Test dopasowania bez polskich znaków
        self.assertEqual(
            przypisz_kategorie("Opinia o panu Cielemeckim", {
                "PRACOWNICY": ["Jan Cielemęcki"],
                "DZIALY": ["Serwis"]
            }),
            "Jan Cielemęcki"
        )

    def test_deklinacja_nazwisk_meskich(self):
        # "kowalskiego" -> "Jan Kowalski"
        self.assertEqual(
            przypisz_kategorie("Robota wykonana przez Kowalskiego była super", {
                "PRACOWNICY": ["Jan Kowalski"],
                "DZIALY": ["Serwis"]
            }),
            "Jan Kowalski"
        )

    def test_obocznosci_samogloskowe_imion(self):
        # "Mariusza" -> "Mariusz Cudny"
        self.assertEqual(
            przypisz_kategorie("Świetny kontakt z panem Mariuszem", {
                "PRACOWNICY": ["Mariusz Cudny"],
                "DZIALY": ["Serwis"]
            }),
            "Mariusz Cudny"
        )

    def test_obocznosci_nazwisk(self):
        # "Rostka" -> "Maciej Rostek" (wykorzystuje fuzzy fallback)
        self.assertEqual(
            przypisz_kategorie("Poproście o pana Rostka, super fachowiec", {
                "PRACOWNICY": ["Maciej Rostek"],
                "DZIALY": ["Serwis"]
            }),
            "Maciej Rostek"
        )

    def test_odmiana_dzialow(self):
        # "serwisie" -> "Serwis"
        self.assertEqual(
            przypisz_kategorie("Bardzo pomocni ludzie w serwisie", {
                "PRACOWNICY": ["Maciej Rostek"],
                "DZIALY": ["Serwis"]
            }),
            "Serwis"
        )

    def test_brak_polskich_znakow_dzialy(self):
        # "dzial handlu" -> "Dział handlu"
        self.assertEqual(
            przypisz_kategorie("Najlepszy dzial handlu w mieście!", {
                "PRACOWNICY": [],
                "DZIALY": ["Dział handlu"]
            }),
            "Dział handlu"
        )

    def test_priorytet_pracownika_nad_dzialem_zlozone(self):
        # Zdanie zawiera i pracownika (Mariusz) i dział (serwis) -> ma przypisać do pracownika
        self.assertEqual(
            przypisz_kategorie("Polecam pana Mariusza z serwisu blacharskiego", {
                "PRACOWNICY": ["Mariusz Cudny"],
                "DZIALY": ["Serwis"]
            }),
            "Mariusz Cudny"
        )

    def test_precyzja_fuzzy_matching_eryk_very(self):
        # Słowo "very" nie powinno zostać dopasowane do imienia "Eryk"
        self.assertEqual(
            przypisz_kategorie("The service was very good indeed", {
                "PRACOWNICY": ["Eryk Nowak"],
                "DZIALY": ["Serwis"]
            }),
            "Ogólne"
        )
        # Słowo "Erykowi" powinno zostać poprawnie dopasowane przez dopasowanie rdzeniowe
        self.assertEqual(
            przypisz_kategorie("Podziękowania dla pana Erykowi za pomoc", {
                "PRACOWNICY": ["Eryk Nowak"],
                "DZIALY": ["Serwis"]
            }),
            "Eryk Nowak"
        )


class TestConfigManager(unittest.TestCase):
    """Testy ładowania i walidacji konfiguracji."""

    def test_walidacja_uzupelnia_brakujace_klucze(self):
        partial_config = {
            "API_KEY": "test-key",
            "CSV_DATABASE": "test.csv"
        }
        
        original_file = config_manager.CONFIG_FILE
        test_file = "test_config_temp.json"
        config_manager.CONFIG_FILE = test_file
        
        try:
            with open(test_file, 'w', encoding='utf-8') as f:
                json.dump(partial_config, f)
            
            loaded = config_manager.load_config()
            
            # Powinny być uzupełnione domyślnymi wartościami
            self.assertIn("EXCEL_FILE", loaded)
            self.assertIn("LOKALIZACJE", loaded)
            self.assertIn("PRACOWNICY", loaded)
            self.assertIn("DZIALY", loaded)
            # Oryginalne wartości zachowane
            self.assertEqual(loaded["API_KEY"], "test-key")
        finally:
            config_manager.CONFIG_FILE = original_file
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_uszkodzony_json_zwraca_domyslne(self):
        original_file = config_manager.CONFIG_FILE
        test_file = "test_config_broken.json"
        config_manager.CONFIG_FILE = test_file
        
        try:
            with open(test_file, 'w') as f:
                f.write("{invalid json content!!!")
            
            loaded = config_manager.load_config()
            self.assertEqual(loaded, config_manager.DEFAULT_CONFIG)
        finally:
            config_manager.CONFIG_FILE = original_file
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_brakujacy_plik_tworzy_domyslny(self):
        original_file = config_manager.CONFIG_FILE
        test_file = "test_config_nonexistent.json"
        config_manager.CONFIG_FILE = test_file
        
        try:
            if os.path.exists(test_file):
                os.remove(test_file)
            
            loaded = config_manager.load_config()
            self.assertEqual(loaded, config_manager.DEFAULT_CONFIG)
            # Plik powinien zostać utworzony
            self.assertTrue(os.path.exists(test_file))
        finally:
            config_manager.CONFIG_FILE = original_file
            if os.path.exists(test_file):
                os.remove(test_file)


class TestMapujRecenzje(unittest.TestCase):
    """Testy mapowania surowej recenzji z GBP API."""

    def test_pelne_prawidlowe_dane_rating_string(self):
        from api_manager import mapuj_recenzje
        r = {
            "reviewId": "rec-123",
            "reviewer": {"displayName": "Jan Kowal"},
            "starRating": "FIVE",
            "comment": "Super!",
            "createTime": "2026-06-08T12:00:00Z"
        }
        res = mapuj_recenzje(r, "Warszawa", {})
        self.assertEqual(res["ReviewID"], "rec-123")
        self.assertEqual(res["Autor"], "Jan Kowal")
        self.assertEqual(res["Ocena"], 5)
        self.assertEqual(res["Lokalizacja"], "Warszawa")
        self.assertEqual(res["Tresc"], "Super!")

    def test_star_rating_numeryczny(self):
        from api_manager import mapuj_recenzje
        r1 = {"reviewId": "1", "starRating": 4}
        r2 = {"reviewId": "2", "starRating": "3"}
        r3 = {"reviewId": "3", "starRating": "INVALID"}
        
        self.assertEqual(mapuj_recenzje(r1, "L", {})["Ocena"], 4)
        self.assertEqual(mapuj_recenzje(r2, "L", {})["Ocena"], 3)
        self.assertEqual(mapuj_recenzje(r3, "L", {})["Ocena"], 0)

    def test_brak_lub_none_reviewer(self):
        from api_manager import mapuj_recenzje
        r_none = {
            "reviewId": "1",
            "reviewer": None
        }
        r_missing = {
            "reviewId": "2"
        }
        self.assertEqual(mapuj_recenzje(r_none, "L", {})["Autor"], "Anonim")
        self.assertEqual(mapuj_recenzje(r_missing, "L", {})["Autor"], "Anonim")

    def test_brak_komentarza_i_daty(self):
        from api_manager import mapuj_recenzje
        r = {"reviewId": "1"}
        res = mapuj_recenzje(r, "L", {})
        self.assertEqual(res["Tresc"], "")
        self.assertEqual(res["Data"], "")


class TestUpdateManager(unittest.TestCase):
    """Testy modułu aktualizacji (update_manager)."""

    @unittest.mock.patch('update_manager.requests.get')
    def test_check_for_updates_newer_version(self, mock_get):
        # Symulacja nowszej wersji na serwerze
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "version": "9.9",
            "download_url": "https://example.com/update.zip",
            "changelog": "Nowe funkcje"
        }
        mock_get.return_value = mock_response

        res = update_manager.check_for_updates("https://dummy.url")
        self.assertIsNotNone(res)
        self.assertEqual(res["version"], "9.9")
        self.assertEqual(res["download_url"], "https://example.com/update.zip")

    @unittest.mock.patch('update_manager.requests.get')
    def test_check_for_updates_older_version(self, mock_get):
        # Symulacja starszej wersji na serwerze
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "version": "1.0",
            "download_url": "https://example.com/update.zip",
            "changelog": "Stara wersja"
        }
        mock_get.return_value = mock_response

        res = update_manager.check_for_updates("https://dummy.url")
        self.assertIsNone(res)

    @unittest.mock.patch('update_manager.requests.get')
    @unittest.mock.patch('update_manager.subprocess.Popen')
    @unittest.mock.patch('update_manager.zipfile.ZipFile')
    def test_download_and_install_update(self, mock_zip, mock_popen, mock_get):
        # Symulacja pobierania pliku ZIP i uruchomienia instalatora PowerShell
        mock_response = unittest.mock.MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"dummy data"]
        mock_get.return_value = mock_response

        with unittest.mock.patch('update_manager.tempfile.mkdtemp', return_value="dummy_temp"), \
             unittest.mock.patch('update_manager.os.makedirs'), \
             unittest.mock.patch('update_manager.os.listdir', return_value=[]), \
             unittest.mock.patch('builtins.open', unittest.mock.mock_open()):
             
            success = update_manager.download_and_install_update("https://example.com/update.zip")
            self.assertTrue(success)

            # Sprawdzamy czy popen uruchomił skrót powershell z odpowiednimi flagami
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], "powershell")
            self.assertIn("-ExecutionPolicy", args)
            self.assertIn("Bypass", args)


class TestLoggingAndRetention(unittest.TestCase):
    """Testy logowania klasyfikacji oraz mechanizmu retencji logów."""

    @unittest.mock.patch('api_manager.os.makedirs')
    @unittest.mock.patch('api_manager.os.listdir')
    @unittest.mock.patch('api_manager.os.remove')
    @unittest.mock.patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_log_review_classification_and_retention(self, mock_file, mock_remove, mock_listdir, mock_makedirs):
        from api_manager import _log_review_classification
        import datetime
        
        # Symulacja listy plików w folderze logs
        now_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        mock_listdir.return_value = [
            "review_2020-01-01.log",
            f"review_{now_date_str}.log",
            "other_file.txt"
        ]
        
        _log_review_classification("Test message")
        
        # Sprawdzamy czy spróbowano otworzyć plik z dzisiejszą datą
        expected_log_file = f"logs/review_{now_date_str}.log"
        mock_file.assert_called_with(expected_log_file, "a", encoding="utf-8")
        
        # Sprawdzamy czy usunięto stary log
        mock_remove.assert_called_once_with(os.path.join("logs", "review_2020-01-01.log"))


if __name__ == "__main__":
    unittest.main()
