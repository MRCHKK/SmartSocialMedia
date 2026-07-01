# update_manager.py
import requests
import logging
import os
import zipfile
import subprocess
import tempfile
import sys

logger = logging.getLogger(__name__)

VERSION = "3.7"
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
        
        ps_path = os.path.join(temp_dir, "updater.ps1")
        
        exe_name = os.path.basename(current_exe)
        
        if is_exe:
            start_command = f'Start-Process -FilePath "{current_exe}"'
        else:
            main_script = os.path.join(app_dir, "main_gui.py")
            start_command = f'Start-Process -FilePath "py" -ArgumentList `"{main_script}`"'

        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ps_content = f"""[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "SmartSocialMedia Auto-Updater"

Write-Host "[Self-Updater] Czekam na zamkniecie aplikacji..." -ForegroundColor Cyan

$exeName = "{exe_name}"
$processName = [System.IO.Path]::GetFileNameWithoutExtension($exeName)

while (Get-Process -Name $processName -ErrorAction SilentlyContinue) {{
    Start-Sleep -Seconds 1
}}
Start-Sleep -Seconds 1

$src = "{src_dir}"
$dest = "{app_dir}"
$logPath = Join-Path $dest "logs\\update.log"

try {{
    $logDir = Split-Path $logPath
    if (!(Test-Path $logDir)) {{
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    }}
    
    "[{now_str}] Rozpoczecie aktualizacji z $src do $dest" | Out-File -Append -FilePath $logPath -Encoding utf8
    
    Write-Host "[Self-Updater] Kopiowanie plikow..." -ForegroundColor Yellow
    
    $files = Get-ChildItem -Path $src -Recurse | Where-Object {{ !$_.PSIsContainer }}
    $total = $files.Count
    $current = 0
    
    $copiedCount = 0
    $skippedCount = 0
    
    foreach ($file in $files) {{
        $current++
        $percent = ($current / $total) * 100
        
        $relPath = $file.FullName.Substring($src.Length).TrimStart([System.IO.Path]::DirectorySeparatorChar)
        
        Write-Progress -Activity "Aktualizowanie SmartSocialMedia" -Status "Analizowanie: $relPath" -PercentComplete $percent
        
        $target = Join-Path $dest $relPath
        
        $shouldCopy = $true
        if (Test-Path $target) {{
            $targetFile = Get-Item $target
            if ($file.Length -eq $targetFile.Length) {{
                $srcHash = (Get-FileHash -Path $file.FullName -Algorithm MD5).Hash
                $dstHash = (Get-FileHash -Path $target -Algorithm MD5).Hash
                if ($srcHash -eq $dstHash) {{
                    $shouldCopy = $false
                }}
            }}
        }}
        
        if ($shouldCopy) {{
            $targetDir = Split-Path $target
            if (!(Test-Path $targetDir)) {{
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }}
            Copy-Item -Path $file.FullName -Destination $target -Force
            $copiedCount++
        }} else {{
            $skippedCount++
        }}
    }}
    
    "[{now_str}] Aktualizacja zakonczona sukcesem. Skopiowano: $copiedCount, Pominieto: $skippedCount" | Out-File -Append -FilePath $logPath -Encoding utf8
    Write-Host "[Self-Updater] Aktualizacja zakonczona sukcesem! (Skopiowano: $copiedCount, Pominieto: $skippedCount)" -ForegroundColor Green
    
    Write-Host "[Self-Updater] Uruchamianie aplikacji..." -ForegroundColor Cyan
    {start_command}
    
}} catch {{
    "[{now_str}] Blad aktualizacji: $_" | Out-File -Append -FilePath $logPath -Encoding utf8
    Write-Host "X Blad instalacji: $_" -ForegroundColor Red
    Write-Host "Szczegoly bledu zostaly zapisane w pliku: $logPath" -ForegroundColor Yellow
    Read-Host "Nacisnij klawisz Enter, aby zamknac..."
    exit 1
}} finally {{
    # Czyszczenie folderu tymczasowego w osobnym procesie w tle
    Start-Process cmd.exe -ArgumentList "/c timeout /t 2 /nobreak >nul & rmdir /s /q `"{temp_dir}`"" -WindowStyle Hidden
}}
"""
        
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(ps_content)
            
        print("[Self-Updater] Wygenerowano updater.ps1. Uruchamiam proces instalacji...")
        
        # Uruchamiamy powershell w nowym konsolowym oknie
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
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
