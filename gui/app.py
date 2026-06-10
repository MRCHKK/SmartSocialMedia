import customtkinter as ctk
import sys
import update_manager

from gui.views.main_view import MainView
from gui.views.settings_view import SettingsView
from gui.views.reviews_view import ReviewsView
from gui.views.sheets_view import SheetsView

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Smart Social Media — Google Reviews Manager")
        self.geometry("1100x750")
        self.minsize(950, 600)
        
        # Konfiguracja głównego układu Grid: 
        # Kolumna 0: Sidebar (stała szerokość), Kolumna 1: Panel Zawartości (dynamiczna)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)

        # Tworzenie paska bocznego
        self._build_sidebar()

        # Ramka (Kontener) przechowująca różne widoki
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        
        # Inicjalizacja wszystkich widoków aplikacji
        self.views = {
            "main": MainView(master=self.content_frame, app_root=self),
            "reviews": ReviewsView(master=self.content_frame),
            "sheets": SheetsView(master=self.content_frame, app_root=self),
            "settings": SettingsView(master=self.content_frame)
        }

        # Ustawiamy domyślny widok
        self.show_view("main")
        
        # Uruchom automatyczne odpytywanie Google API co 5 minut (300 000 ms)
        self.after(300000, self._auto_fetch_loop)
        
        # Sprawdzenie aktualizacji 2 sekundy po uruchomieniu
        self.after(2000, self._check_updates_startup)

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1e2226")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        # Logo / Tytuł Aplikacji
        logo_label = ctk.CTkLabel(
            self.sidebar_frame, text="SmartSocial", 
            font=("Arial", 24, "bold"), text_color="#5cbaf0"
        )
        logo_label.pack(pady=(35, 0), padx=20, anchor="w")
        
        subtitle = ctk.CTkLabel(
            self.sidebar_frame, text="Reviews Manager Pro", 
            font=("Arial", 13), text_color="#aaaaaa"
        )
        subtitle.pack(pady=(0, 40), padx=20, anchor="w")

        # Przyciski nawigacyjne
        self.btn_main = ctk.CTkButton(
            self.sidebar_frame, text=" 🏠 Akcje / Start", 
            font=("Arial", 15, "bold"), anchor="w", fg_color="transparent",
            text_color="#cccccc", hover_color="#2c333a", height=45, corner_radius=8,
            command=lambda: self.show_view("main")
        )
        self.btn_main.pack(fill="x", padx=15, pady=6)
        
        self.btn_reviews = ctk.CTkButton(
            self.sidebar_frame, text=" 🔎 Baza Opinii", 
            font=("Arial", 15, "bold"), anchor="w", fg_color="transparent",
            text_color="#cccccc", hover_color="#2c333a", height=45, corner_radius=8,
            command=lambda: self.show_view("reviews")
        )
        self.btn_reviews.pack(fill="x", padx=15, pady=6)

        self.btn_sheets = ctk.CTkButton(
            self.sidebar_frame, text=" 📊 Arkusze", 
            font=("Arial", 15, "bold"), anchor="w", fg_color="transparent",
            text_color="#cccccc", hover_color="#2c333a", height=45, corner_radius=8,
            command=lambda: self.show_view("sheets")
        )
        self.btn_sheets.pack(fill="x", padx=15, pady=6)

        self.btn_settings = ctk.CTkButton(
            self.sidebar_frame, text=" ⚙️ Ustawienia", 
            font=("Arial", 15, "bold"), anchor="w", fg_color="transparent",
            text_color="#cccccc", hover_color="#2c333a", height=45, corner_radius=8,
            command=lambda: self.show_view("settings")
        )
        self.btn_settings.pack(fill="x", padx=15, pady=6)
        
        # Separator i wersja na dole
        bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=20)
        ctk.CTkLabel(bottom_frame, text=f"Wersja {update_manager.VERSION}", font=("Arial", 11), text_color="#666666").pack()

    def show_view(self, view_name):
        active_color = "#3a7ebf"
        inactive_color = "transparent"

        btn_map = {
            "main": self.btn_main,
            "reviews": self.btn_reviews,
            "sheets": self.btn_sheets,
            "settings": self.btn_settings,
        }
        for name, btn in btn_map.items():
            is_active = (name == view_name)
            btn.configure(
                fg_color=active_color if is_active else inactive_color,
                text_color="white" if is_active else "#cccccc"
            )

        for view in self.views.values():
            view.pack_forget()

        self.views[view_name].pack(fill="both", expand=True)

        # Dodatkowe akcje przy wejściu w widok
        if view_name == "reviews":
            self.views["reviews"].load_data()
        elif view_name == "sheets":
            self.views["sheets"].refresh_files()

    def _auto_fetch_loop(self):
        """Uruchamia pobieranie opinii w tle co 5 minut, aby wysyłać powiadomienia na pulpit."""
        def task():
            try:
                import api_manager
                api_manager.pobierz_z_google()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Błąd w tle (auto-fetch): {e}")
            finally:
                # Ponowne zaplanowanie za równe 5 minut
                if self.winfo_exists():
                    self.after(300000, self._auto_fetch_loop)
        
        import threading
        threading.Thread(target=task, daemon=True).start()

    def _check_updates_startup(self):
        import threading
        import webbrowser
        from tkinter import messagebox

        def task():
            update_info = update_manager.check_for_updates()
            if update_info:
                version = update_info["version"]
                url = update_info["download_url"]
                changelog = update_info.get("changelog", "Brak szczegółów zmian.")
                
                def show_popup():
                    if messagebox.askyesno(
                        "Dostępna aktualizacja!",
                        f"Wykryto nową wersję aplikacji: {version} (aktualna wersja: {update_manager.VERSION}).\n\n"
                        f"Co nowego:\n{changelog}\n\n"
                        "Czy chcesz automatycznie zainstalować tę aktualizację teraz?"
                    ):
                        messagebox.showinfo(
                            "Instalowanie aktualizacji",
                            "Aktualizacja jest pobierana i instalowana w tle. Program wyłączy się automatycznie po zakończeniu pobierania."
                        )
                        
                        def download_and_restart():
                            success = update_manager.download_and_install_update(url)
                            if success:
                                self.after(0, self.destroy)
                            else:
                                self.after(0, lambda: messagebox.showerror(
                                    "Błąd aktualizacji",
                                    "Wystąpił błąd podczas pobierania lub instalowania aktualizacji."
                                ))
                        
                        threading.Thread(target=download_and_restart, daemon=True).start()
                
                if self.winfo_exists():
                    self.after(0, show_popup)

        threading.Thread(target=task, daemon=True).start()
