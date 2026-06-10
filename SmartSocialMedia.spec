# SmartSocialMedia.spec
# Plik konfiguracyjny PyInstaller
# Uruchom build: py -m PyInstaller SmartSocialMedia.spec

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Zbierz wszystkie pliki danych CustomTkinter (motywy, czcionki)
ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    ['main_gui.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        # Ikonka aplikacji
        ('assets', 'assets'),
        # Pliki CustomTkinter (wymagane!)
        *ctk_datas,
    ],
    hiddenimports=[
        # Google Auth / OAuth2
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.oauth2',
        'google.oauth2.credentials',
        'google_auth_oauthlib',
        'google_auth_oauthlib.flow',
        # Plyer (powiadomienia Windows)
        'plyer',
        'plyer.platforms',
        'plyer.platforms.win',
        'plyer.platforms.win.notification',
        # Pandas / openpyxl
        'pandas',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.chart',
        # Inne
        'dateutil',
        'dateutil.tz',
        'difflib',
        'tkcalendar',
        'babel.numbers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Wyklucz niepotrzebne moduły (zmniejsza rozmiar)
        'tkinter.test',
        'unittest',
        'test',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartSocialMedia',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Brak czarnego okna konsoli
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico', # Ikonka pliku .exe
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SmartSocialMedia',  # Nazwa folderu w dist/
)
