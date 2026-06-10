import customtkinter as ctk
import logging
import os
import ctypes
from gui.app import App

# Upewnienie się że logger zbierze wszystko do folderu z logami
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding='utf-8'),
    ]
)

ICON_PATH = os.path.join("assets", "icon.ico")

if __name__ == "__main__":
    # Ustawienie AppUserModelID — Windows pokazuje ikonkę aplikacji w taskbarze zamiast python.exe
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SmartSocialMedia.ReviewsManager.1.0")
    except Exception:
        pass
    # Główne ustawienia systemowe wizualizacji dla całego CustomTkinter
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Uruchomienie zrefaktoryzowanego, ładnego interfejsu
    app = App()

    # Ustawienie ikonki okna (pasek tytułu + taskbar)
    if os.path.exists(ICON_PATH):
        try:
            app.iconbitmap(ICON_PATH)
        except Exception:
            pass  # Nie blokuj startu jeśli coś pójdzie nie tak z ikonką

    app.mainloop()