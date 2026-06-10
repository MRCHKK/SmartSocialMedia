# gui/views/main_view.py
import customtkinter as ctk
import threading
import logging

import api_manager

logger = logging.getLogger(__name__)


class MainView(ctk.CTkFrame):
    def __init__(self, master, app_root, **kwargs):
        super().__init__(master, **kwargs)
        self.app_root = app_root
        self.configure(fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.main_panel.grid(row=0, column=0, sticky="nsew")

        self._build_panel()
        self.app_root.after(200, self.refresh_locations)

    def _build_panel(self):
        # --- Przycisk akcji ---
        cards_frame = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 20))
        cards_frame.grid_columnconfigure(0, weight=1)

        btn1 = ctk.CTkButton(
            cards_frame,
            text="☁️ Pobierz z Google Business Profile",
            font=("Arial", 15, "bold"), height=80, corner_radius=8,
            fg_color="#2a5b84", hover_color="#1d405c",
            command=self.run_api
        )
        btn1.grid(row=0, column=0, sticky="ew")

        # --- Sekcja Lokalizacji ---
        locations_wrapper = ctk.CTkFrame(self.main_panel, fg_color="#1e1e1e", corner_radius=10)
        locations_wrapper.pack(fill="both", expand=True)

        header_frame = ctk.CTkFrame(locations_wrapper, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(10, 0))

        ctk.CTkLabel(
            header_frame, text="📍 Zapisane Lokalizacje (Status)",
            font=("Arial", 15, "bold"), text_color="#aaaaaa", anchor="w"
        ).pack(side="left")

        ctk.CTkButton(
            header_frame, text="Odśwież", width=80, height=28,
            corner_radius=6, fg_color="#444444", hover_color="#333333",
            command=self.refresh_locations
        ).pack(side="right")

        self.locations_frame = ctk.CTkScrollableFrame(locations_wrapper, fg_color="transparent")
        self.locations_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Zadania Asynchroniczne ---
    def run_api(self):
        print("\n--- Rozpoczynam pobieranie z Google Business Profile API ---")
        def task():
            try:
                api_manager.pobierz_z_google()
            except FileNotFoundError as e:
                logger.error(f"Brak client_secrets.json: {e}")
                print("\n[BŁĄD] Brak pliku autoryzacji OAuth2 — wejdź w Ustawienia i skonfiguruj Google Business Profile API.")
            except Exception as e:
                logger.exception("Błąd podczas pobierania z GBP")
                print(f"\n[BŁĄD KRYTYCZNY] {e}")
        threading.Thread(target=task, daemon=True).start()

    def refresh_locations(self):
        for widget in self.locations_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.locations_frame,
            text="Pobieranie danych z Google Business Profile API...",
            text_color="#777777"
        ).pack(pady=30)

        def task():
            try:
                dane = api_manager.pobierz_szczegoly_lokalizacji()
                self.app_root.after(0, lambda: self._update_locations_ui(dane))
            except Exception as e:
                logger.exception("Błąd pobierania szczegółów lokalizacji")
                self.app_root.after(0, lambda: self._update_locations_ui(error=str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _update_locations_ui(self, dane=None, error=None):
        for widget in self.locations_frame.winfo_children():
            widget.destroy()

        if error:
            ctk.CTkLabel(self.locations_frame, text=f"Błąd: {error}", text_color="#cc4444").pack(pady=20)
            return

        if not dane:
            ctk.CTkLabel(
                self.locations_frame,
                text="Brak skonfigurowanych lokalizacji.\nWejdź w Ustawienia i skonfiguruj Google Business Profile API.",
                text_color="#777777"
            ).pack(pady=20)
            return

        for loc in dane:
            card = ctk.CTkFrame(self.locations_frame, fg_color="#2b3036", corner_radius=8)
            card.pack(fill="x", pady=6, padx=10)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

            ctk.CTkLabel(
                info_frame, text=loc.get("display_name", "Nieznana"),
                font=("Arial", 16, "bold"), text_color="#ffffff", anchor="w"
            ).pack(fill="x")

            ctk.CTkLabel(
                info_frame, text=f"Opis własny: {loc.get('custom_name', '')}",
                font=("Arial", 12), text_color="#aaaaaa", anchor="w"
            ).pack(fill="x", pady=(2, 0))

            stats_frame = ctk.CTkFrame(card, fg_color="transparent")
            stats_frame.pack(side="right", padx=15, pady=10)

            rating = loc.get("rating", "—")
            count = loc.get("userRatingCount", "—")

            ctk.CTkLabel(
                stats_frame, text=f"{rating} ⭐",
                font=("Arial", 20, "bold"), text_color="#f5c518"
            ).pack()

            ctk.CTkLabel(
                stats_frame, text=f"{count} opinii",
                font=("Arial", 12), text_color="#cccccc"
            ).pack()
