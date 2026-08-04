import customtkinter as ctk
import logging
import os
import sys
import ctypes

# Upewnienie się że logger zbierze wszystko do folderu z logami
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("GLOBAL")

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Przechwytuje każdy niespodziewany błąd przed wykrzaczeniem aplikacji i zapisuje pełny traceback do app.log."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("KRYTYCZNY NIESPODZIEWANY BŁĄD APLIKACJI (CRASH):", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_uncaught_exception

ICON_PATH = os.path.join("assets", "icon.ico")

if __name__ == "__main__":
    logger.info("--- Uruchamianie aplikacji SmartSocialMedia ---")
    try:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SmartSocialMedia.ReviewsManager.1.0")
        except Exception as e:
            logger.warning(f"Błąd SetCurrentProcessExplicitAppUserModelID: {e}")

        logger.info("Konfigurowanie motywu CustomTkinter...")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        logger.info("Importowanie klasy App z gui.app...")
        from gui.app import App
        
        logger.info("Inicjalizacja obiektu App()...")
        app = App()

        if os.path.exists(ICON_PATH):
            try:
                app.iconbitmap(ICON_PATH)
            except Exception as e:
                logger.warning(f"Nie udało się ustawić ikony: {e}")

        logger.info("Uruchamianie pętli głównej (app.mainloop())...")
        app.mainloop()
        logger.info("--- Zamknięcie aplikacji SmartSocialMedia ---")
    except Exception as e:
        logger.critical(f"Błąd krytyczny podczas uruchamiania mainloop: {e}", exc_info=True)
    finally:
        logging.shutdown()