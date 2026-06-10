# update_manager.py
import requests
import logging
import os
import zipfile
import subprocess
import tempfile
import sys

logger = logging.getLogger(__name__)

VERSION = "3.3"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/MRCHKK/SmartSocialMedia/refs/heads/main/version.json"

def download_and_install_update(download_url: str) -> bool:
    """
    Pobiera plik ZIP z download_url, wypakowuje go do katalogu tymczasowego,
    tworzy skrypt updater.bat i uruchamia go w tle, po czym zwraca True.
    """


    try:
        print(f"[Self-Updater] Pobieranie aktualizacji z: {download_url}")
        response = requests.get(download_url, timeout=60, stream=True)
        if response.status_code != 200:
            print(f"[Self-Updater] Błąd pobierania: HTTP {response.status_code}")
            return False
        
        temp_dir = tempfile.mkdtemp(prefix="ssm_update_")
        zip_path = os.path.join(temp_dir, "update.zip")
        
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print("[Self-Updater] Pobrano plik ZIP.")
        
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("[Self-Updater] Wypakowano pliki.")
        
        current_exe = sys.executable
        app_dir = os.path.dirname(os.path.abspath(current_exe))
        is_exe = current_exe.endswith(".exe")
        
        if not is_exe:
            # W środowisku deweloperskim sys.executable to python.exe, więc bierzemy katalog roboczy
            app_dir = os.path.abspath(os.getcwd())
        
        src_dir = extract_dir
        subdirs = [d for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
        # Jeśli zip zawiera pojedynczy folder główny, kopiujemy z jego wnętrza
        if len(subdirs) == 1 and len(os.listdir(extract_dir)) == 1:
            src_dir = os.path.join(extract_dir, subdirs[0])
            
        print(f"[Self-Updater] Ścieżka źródłowa kopiowania: {src_dir}")
        print(f"[Self-Updater] Ścieżka docelowa kopiowania: {app_dir}")
        
        bat_path = os.path.join(temp_dir, "updater.bat")
        
        # Skrypt wsadowy czekający na zamknięcie procesu głównego
        bat_content = f"""@echo off
chcp 65001 > nul
echo [Self-Updater] Czekam na wyłączenie aplikacji...
:wait
tasklist /FI "IMAGENAME eq {os.path.basename(current_exe)}" 2>NUL | find /I /N "{os.path.basename(current_exe)}">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait
)
timeout /t 1 /nobreak >nul

echo [Self-Updater] Instalacja aktualizacji (kopiowanie plików)...
xcopy /y /s /e "{src_dir}\\*" "{app_dir}\\" > nul

echo [Self-Updater] Uruchamianie zaktualizowanej aplikacji...
"""

        if is_exe:
            bat_content += f'start "" "{current_exe}"\n'
        else:
            main_script = os.path.join(app_dir, "main_gui.py")
            bat_content += f'start "" py "{main_script}"\n'
            
        bat_content += f"""echo [Self-Updater] Czyszczenie plików tymczasowych...
start /b "" cmd /c del /f /q "{bat_path}" ^& rmdir /s /q "{temp_dir}"
exit
"""
        
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
            
        print("[Self-Updater] Wygenerowano updater.bat. Uruchamiam proces instalacji...")
        
        # Uruchamiamy .bat jako całkowicie odseparowany proces
        subprocess.Popen(
            [bat_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True
        )
        return True
    except Exception as e:
        print(f"[Self-Updater] Błąd krytyczny podczas auto-aktualizacji: {e}")
        logger.exception("Błąd auto-aktualizacji")
        return False

def check_for_updates(update_url: str = DEFAULT_UPDATE_URL) -> dict:
    """
    Sprawdza, czy dostępna jest nowsza wersja aplikacji.
    Zwraca słownik z informacjami o aktualizacji, jeśli jest dostępna, w przeciwnym razie None.
    """
    print(f"[Update Checker] Sprawdzam aktualizacje pod adresem: {update_url}")
    print(f"[Update Checker] Lokalna wersja aplikacji: {VERSION}")
    try:
        response = requests.get(update_url, timeout=5)
        print(f"[Update Checker] Status odpowiedzi HTTP: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"[Update Checker] Pobrane dane: {data}")
            online_version = data.get("version", "")
            download_url = data.get("download_url", "")
            changelog = data.get("changelog", "")
            
            try:
                local_f = float(VERSION)
                online_f = float(online_version)
                print(f"[Update Checker] Porównanie float: online({online_f}) vs lokalna({local_f})")
                if online_f > local_f:
                    print("[Update Checker] Wykryto nowszą wersję!")
                    return {
                        "version": online_version,
                        "download_url": download_url,
                        "changelog": changelog
                    }
            except ValueError:
                print(f"[Update Checker] Porównanie tekstowe: online({online_version}) vs lokalna({VERSION})")
                if online_version > VERSION:
                    print("[Update Checker] Wykryto nowszą wersję!")
                    return {
                        "version": online_version,
                        "download_url": download_url,
                        "changelog": changelog
                    }
        else:
            print(f"[Update Checker] Serwer zwrócił status inny niż 200: {response.status_code}")
    except Exception as e:
        print(f"[Update Checker] Wyjątek podczas sprawdzania aktualizacji: {e}")
        logger.warning(f"Błąd podczas sprawdzania aktualizacji: {e}")
    return None
