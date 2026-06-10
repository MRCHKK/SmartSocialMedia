# gui/views/settings_view.py
# pyrefly: ignore [missing-import]
import customtkinter as ctk
import logging
import threading
import os
from tkinter import messagebox, filedialog

import config_manager
import auth_manager
from gui.components.dynamic_dict_editor import DynamicDictEditor
from gui.components.dynamic_list_editor import DynamicListEditor

logger = logging.getLogger(__name__)


class LocationsImportDialog(ctk.CTkToplevel):
    def __init__(self, master, lokalizacje_lista, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Wykryto lokalizacje GBP")
        self.geometry("600x500")
        self.minsize(450, 350)
        self.resizable(True, True)
        
        # Centrowanie na rodzicu
        self.update_idletasks()
        if master:
            parent = master.winfo_toplevel()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            x = parent_x + (parent_w // 2) - (600 // 2)
            y = parent_y + (parent_h // 2) - (500 // 2)
            self.geometry(f"600x500+{max(0, x)}+{max(0, y)}")
            
        self.attributes('-topmost', True)
        self.grab_set()

        self.confirmed = False
        self.selected_locations = []
        self.checkbox_vars = []

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.grid_rowconfigure(2, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # 1. Nagłówek
        lbl_title = ctk.CTkLabel(
            container,
            text=f"📍 Wykryto {len(lokalizacje_lista)} lokalizacji",
            font=("Arial", 16, "bold"),
            text_color="#5cbaf0",
            anchor="w"
        )
        lbl_title.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        lbl_desc = ctk.CTkLabel(
            container,
            text="Wybierz lokalizacje do importu. Odznacz te, które chcesz zignorować.\n(Po zatwierdzeniu ustawienia zostaną automatycznie zapisane)",
            font=("Arial", 12),
            text_color="#aaaaaa",
            justify="left",
            anchor="w"
        )
        lbl_desc.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        # 2. Przewijalna ramka
        self.scroll_frame = ctk.CTkScrollableFrame(container, fg_color="#1a222b", corner_radius=8)
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 15))

        for idx, loc in enumerate(lokalizacje_lista, 1):
            item_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            item_frame.pack(fill="x", pady=4, padx=5)
            
            # Lewa strona: Teksty informacyjne
            text_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True)
            
            ctk.CTkLabel(
                text_frame,
                text=f"• {loc['title']}",
                font=("Arial", 13, "bold"),
                text_color="#ffffff",
                anchor="w",
                justify="left"
            ).pack(fill="x")
            
            ctk.CTkLabel(
                text_frame,
                text=f"  ID: {loc['name']}",
                font=("Consolas", 11),
                text_color="#888888",
                anchor="w",
                justify="left"
            ).pack(fill="x")

            # Prawa strona: Checkbox wyboru
            var = ctk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(
                item_frame,
                text="",
                variable=var,
                width=24,
                fg_color="#1e5c3a",
                hover_color="#144028"
            )
            chk.pack(side="right", padx=10)
            
            self.checkbox_vars.append((loc, var))

        # 3. Przyciski dolne
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_confirm = ctk.CTkButton(
            btn_frame,
            text="Zastąp i Dodaj",
            font=("Arial", 13, "bold"),
            height=38,
            fg_color="#1e5c3a",
            hover_color="#144028",
            command=self._confirm
        )
        self.btn_confirm.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Anuluj",
            font=("Arial", 13),
            height=38,
            fg_color="#444",
            hover_color="#555",
            command=self._cancel
        )
        self.btn_cancel.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        self.confirmed = True
        self.selected_locations = [loc for loc, var in self.checkbox_vars if var.get()]
        self.destroy()

    def _cancel(self):
        self.confirmed = False
        self.destroy()


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="transparent")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=10)

        config = config_manager.load_config()

        # =====================================================================
        # SEKCJA 1: Google Business Profile — Autoryzacja OAuth 2.0
        # =====================================================================
        card_oauth = ctk.CTkFrame(content, corner_radius=10, fg_color="#1a2535")
        card_oauth.pack(fill="x", pady=(0, 20))

        # Nagłówek sekcji
        header_oauth = ctk.CTkFrame(card_oauth, fg_color="transparent")
        header_oauth.pack(fill="x", padx=15, pady=(15, 8))

        ctk.CTkLabel(
            header_oauth,
            text="🔐 Google Business Profile — Autoryzacja OAuth 2.0",
            font=("Arial", 16, "bold"), text_color="#5cbaf0", anchor="w"
        ).pack(side="left", fill="x", expand=True)

        # Wskaźnik statusu autoryzacji
        self.lbl_auth_status = ctk.CTkLabel(
            header_oauth, text="●  Sprawdzanie...",
            font=("Arial", 13, "bold"), text_color="#888888"
        )
        self.lbl_auth_status.pack(side="right", padx=10)

        # Opis
        ctk.CTkLabel(
            card_oauth,
            text=(
                "Google Business Profile API używa OAuth 2.0 zamiast prostego klucza API.\n"
                "Dzięki temu możesz pobierać WSZYSTKIE recenzje bez limitu (darmowe).\n"
                "Wymagane jednorazowe zalogowanie kontem Google, które zarządza wizytówkami."
            ),
            font=("Arial", 12), text_color="#aaaaaa", anchor="w", justify="left"
        ).pack(fill="x", padx=15, pady=(0, 10))

        # Pole ścieżki do client_secrets.json
        self.entry_secrets = self._create_setting_row_with_browse(
            card_oauth,
            "Plik Client Secrets (JSON):",
            config.get("GBP_CLIENT_SECRETS", "client_secrets.json"),
            "Wybierz plik client_secrets.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        # Pole ścieżki do token.json
        self.entry_token = self._create_setting_row(
            card_oauth,
            "Plik tokenu (token.json):",
            config.get("GBP_TOKEN_FILE", "data/token.json")
        )

        # Przyciski akcji OAuth
        btn_frame = ctk.CTkFrame(card_oauth, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(5, 15))

        self.btn_authorize = ctk.CTkButton(
            btn_frame,
            text="🌐 Autoryzuj konto Google (otwiera przeglądarkę)",
            font=("Arial", 13, "bold"), height=42, corner_radius=8,
            fg_color="#1a4a8a", hover_color="#12336b",
            command=self._run_oauth_flow
        )
        self.btn_authorize.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_revoke = ctk.CTkButton(
            btn_frame,
            text="🗑️ Wyloguj / Resetuj token",
            font=("Arial", 13), height=42, corner_radius=8,
            fg_color="#5a2020", hover_color="#3d1515",
            command=self._revoke_token
        )
        self.btn_revoke.pack(side="left", padx=(0, 0))

        # Auto-wykrywanie lokalizacji
        self.btn_detect_locations = ctk.CTkButton(
            card_oauth,
            text="🔍 Wykryj lokalizacje z GBP (pobierz listę automatycznie)",
            font=("Arial", 13), height=38, corner_radius=8,
            fg_color="#1e5c3a", hover_color="#144028",
            command=self._detect_locations
        )
        self.btn_detect_locations.pack(fill="x", padx=15, pady=(0, 15))

        # =====================================================================
        # SEKCJA 2: Ustawienia plików
        # =====================================================================
        card_basic = ctk.CTkFrame(content, corner_radius=10, fg_color="#262b30")
        card_basic.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            card_basic, text="📁 Ustawienia plików i powiadomień",
            font=("Arial", 16, "bold"), text_color="#3a7ebf", anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 10))

        self.entry_csv = self._create_setting_row(card_basic, "Nazwa pliku (Baza CSV):", config.get("CSV_DATABASE", ""))
        self.entry_excel = self._create_setting_row(card_basic, "Nazwa pliku eksportu (Excel):", config.get("EXCEL_FILE", ""))

        # Powiadomienia
        self.check_notifications_var = ctk.BooleanVar(value=config.get("NOTIFICATIONS_ENABLED", True))
        self.check_notifications = ctk.CTkCheckBox(
            card_basic,
            text="Włącz dymki powiadomień na pulpicie dla negatywnych opinii (<= 3 gwiazdki)",
            variable=self.check_notifications_var, font=("Arial", 13)
        )
        self.check_notifications.pack(anchor="w", padx=20, pady=(10, 15))

        # =====================================================================
        # SEKCJA 3: Edytor Lokalizacji GBP
        # =====================================================================
        card_lokalizacje = ctk.CTkFrame(content, corner_radius=10, fg_color="#262b30", height=10)
        card_lokalizacje.pack(fill="x", pady=10)

        ctk.CTkLabel(
            card_lokalizacje,
            text="📍 Lokalizacje Obiektów (Google Business Profile)",
            font=("Arial", 16, "bold"), text_color="#3a7ebf", anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            card_lokalizacje,
            text='Format klucza: "accounts/{accountId}/locations/{locationId}"\nUżyj przycisku "Wykryj lokalizacje z GBP" powyżej aby pobrać automatycznie.',
            font=("Arial", 11), text_color="#777777", anchor="w", justify="left"
        ).pack(fill="x", padx=15, pady=(0, 8))

        self.location_employee_editors = {}
        self.location_employee_frames = {}

        self.editor_lokalizacje = DynamicDictEditor(
            card_lokalizacje,
            "Lokalizacje",
            "accounts/.../locations/... (GBP Location Name)",
            "Czytelna nazwa dla biznesu",
            config.get("LOKALIZACJE", {}),
            on_change_callback=lambda: self.rebuild_employee_editors()
        )
        self.editor_lokalizacje.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # =====================================================================
        # SEKCJA 4: Klasyfikacja Pracowników per Lokalizacja
        # =====================================================================
        self.pracownicy_section_container = ctk.CTkFrame(content, fg_color="transparent")
        self.pracownicy_section_container.pack(fill="x", pady=10)
        self.rebuild_employee_editors()

        # =====================================================================
        # SEKCJA 5: Edytor Działów
        # =====================================================================
        card_dzialy = ctk.CTkFrame(content, corner_radius=10, fg_color="#262b30", height=10)
        card_dzialy.pack(fill="x", pady=10)
        self.editor_dzialy = DynamicListEditor(
            card_dzialy, "Klasyfikacja: Działy / Usługi",
            "Nazwa działu",
            config.get("DZIALY", [])
        )
        self.editor_dzialy.pack(fill="both", expand=True, padx=10, pady=10)

        # =====================================================================
        # Przycisk Reklasyfikacja
        # =====================================================================
        self.btn_reclassify = ctk.CTkButton(
            content, text="🔄 Reklasyfikuj istniejącą bazę (zastosuj nowe reguły do zapisanych opinii)",
            font=("Arial", 13), height=40, corner_radius=8,
            fg_color="#3a7ebf", hover_color="#2a5b84",
            command=self._run_reclassification
        )
        self.btn_reclassify.pack(pady=(20, 0), fill="x", padx=10)

        # =====================================================================
        # Przycisk ZAPISZ
        # =====================================================================
        btn_zapisz = ctk.CTkButton(
            content, text="ZAPISZ KONFIGURACJĘ",
            font=("Arial", 16, "bold"), height=50, corner_radius=8,
            fg_color="#1d8f34", hover_color="#146624",
            command=lambda: self.save_settings()
        )
        btn_zapisz.pack(pady=(30, 40), fill="x", padx=10)

        # Odśwież status OAuth przy starcie
        self.after(200, self._refresh_auth_status)

        # Przyśpieszenie scrollowania w Ustawieniach
        self.after(500, lambda: self._bind_fast_scroll(self))

    # =========================================================================
    # Pomocnicze metody tworzenia wierszy formularza
    # =========================================================================

    def _create_setting_row(self, parent, label_text, default_val):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(
            row, text=label_text, width=220, anchor="w",
            font=("Arial", 13)
        ).pack(side="left")
        entry = ctk.CTkEntry(row, height=36, font=("Consolas", 12))
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, default_val)
        return entry

    def _create_setting_row_with_browse(self, parent, label_text, default_val, dialog_title, filetypes=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(
            row, text=label_text, width=220, anchor="w",
            font=("Arial", 13)
        ).pack(side="left")
        entry = ctk.CTkEntry(row, height=36, font=("Consolas", 12))
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, default_val)

        def browse():
            path = filedialog.askopenfilename(
                title=dialog_title,
                filetypes=filetypes or [("All files", "*.*")]
            )
            if path:
                entry.delete(0, "end")
                entry.insert(0, path)
                # Automatyczny zapis po wybraniu pliku
                self.save_settings(silent=True)

        ctk.CTkButton(
            row, text="📂 Przeglądaj", width=110, height=36,
            fg_color="#444", hover_color="#555",
            font=("Arial", 12),
            command=browse
        ).pack(side="left", padx=(8, 0))
        return entry

    # =========================================================================
    # Logika OAuth
    # =========================================================================

    def _refresh_auth_status(self):
        """Aktualizuje etykietę statusu autoryzacji OAuth."""
        config = config_manager.load_config()
        token_file = config.get("GBP_TOKEN_FILE", "data/token.json")

        try:
            authorized = auth_manager.is_authorized(token_file)
        except Exception:
            authorized = False

        if authorized:
            self.lbl_auth_status.configure(
                text="●  Autoryzacja aktywna ✓",
                text_color="#2ecc71"
            )
        else:
            self.lbl_auth_status.configure(
                text="●  Brak autoryzacji — wymagane logowanie",
                text_color="#e74c3c"
            )

    def _run_oauth_flow(self):
        """Uruchamia flow OAuth2 w osobnym wątku (by nie blokować GUI)."""
        secrets_file = self.entry_secrets.get().strip()
        token_file = self.entry_token.get().strip()

        if not secrets_file:
            messagebox.showerror("Błąd", "Podaj ścieżkę do pliku client_secrets.json!")
            return

        if not os.path.exists(secrets_file):
            messagebox.showerror(
                "Brak pliku",
                f"Plik '{secrets_file}' nie istnieje!\n\n"
                "Pobierz go z Google Cloud Console:\n"
                "console.cloud.google.com → API & Services → Credentials\n"
                "→ OAuth 2.0 Client IDs (typ: Desktop app) → Pobierz JSON"
            )
            return

        self.btn_authorize.configure(state="disabled", text="⏳ Autoryzacja w toku (przeglądarka)...")
        self.lbl_auth_status.configure(text="●  Oczekiwanie na logowanie (maks. 150s)...", text_color="#f39c12")

        def task():
            try:
                auth_manager.get_credentials(secrets_file, token_file)
                self.after(0, lambda: self._on_auth_success())
            except Exception as e:
                logger.exception("Błąd autoryzacji OAuth2")
                self.after(0, lambda: self._on_auth_error(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_auth_success(self):
        self.btn_authorize.configure(state="normal", text="🌐 Autoryzuj konto Google (otwiera przeglądarkę)")
        self.lbl_auth_status.configure(text="●  Autoryzacja aktywna ✓", text_color="#2ecc71")
        messagebox.showinfo(
            "Sukces!",
            "✅ Autoryzacja zakończona pomyślnie!\n\n"
            "Token zapisany lokalnie. Program będzie odświeżał go automatycznie.\n"
            "Możesz teraz pobierać recenzje z Google Business Profile bez limitu!"
        )

    def _on_auth_error(self, error_msg: str):
        self.btn_authorize.configure(state="normal", text="🌐 Autoryzuj konto Google (otwiera przeglądarkę)")
        self.lbl_auth_status.configure(text="●  Błąd autoryzacji", text_color="#e74c3c")
        messagebox.showerror("Błąd autoryzacji", f"Nie udało się autoryzować:\n\n{error_msg}")

    def _revoke_token(self):
        config = config_manager.load_config()
        token_file = self.entry_token.get().strip() or config.get("GBP_TOKEN_FILE", "data/token.json")

        if not os.path.exists(token_file):
            messagebox.showinfo("Info", "Brak zapisanego tokenu — nie ma czego usuwać.")
            return

        if messagebox.askyesno(
            "Potwierdź wylogowanie",
            "Czy na pewno chcesz usunąć token autoryzacji?\n\n"
            "Przy następnym pobraniu recenzji konieczne będzie ponowne logowanie."
        ):
            auth_manager.revoke_authorization(token_file)
            self._refresh_auth_status()
            messagebox.showinfo("Wylogowano", "Token usunięty. Przy następnym użyciu wymagana będzie ponowna autoryzacja.")

    def _detect_locations(self):
        """Pobiera listę lokalizacji z GBP API i wypełnia edytor."""
        config = config_manager.load_config()
        secrets_file = self.entry_secrets.get().strip() or config.get("GBP_CLIENT_SECRETS", "client_secrets.json")
        token_file = self.entry_token.get().strip() or config.get("GBP_TOKEN_FILE", "data/token.json")

        if not auth_manager.is_authorized(token_file):
            messagebox.showwarning(
                "Brak autoryzacji",
                "Najpierw autoryzuj konto Google!\n"
                "Kliknij przycisk 'Autoryzuj konto Google' powyżej."
            )
            return

        self.btn_detect_locations.configure(state="disabled", text="⏳ Pobieranie lokalizacji z GBP...")

        def task():
            try:
                import api_manager
                lokalizacje_lista = api_manager.pobierz_konta_i_lokalizacje()
                self.after(0, lambda: self._on_locations_detected(lokalizacje_lista))
            except Exception as e:
                logger.exception("Błąd wykrywania lokalizacji GBP")
                self.after(0, lambda: self._on_locations_error(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_locations_detected(self, lokalizacje_lista: list):
        self.btn_detect_locations.configure(
            state="normal",
            text="🔍 Wykryj lokalizacje z GBP (pobierz listę automatycznie)"
        )

        if not lokalizacje_lista:
            messagebox.showinfo("Brak lokalizacji", "Nie znaleziono żadnych lokalizacji w Google Business Profile.")
            return

        # Zbuduj słownik name → title i wstaw do edytora
        nowe_lokalizacje = {loc["name"]: loc["title"] for loc in lokalizacje_lista}

        # Zablokuj scrollowanie rodzica i przechwyć yview_scroll
        self._scroll_blocked = True
        original_yview_scroll = self._parent_canvas.yview_scroll
        self._parent_canvas.yview_scroll = lambda *args, **kwargs: "break"

        try:
            # Pokaż dialog z listą przed zatwierdzeniem
            dialog = LocationsImportDialog(self, lokalizacje_lista)
            self.wait_window(dialog)

            if dialog.confirmed:
                nowe_lokalizacje_wybrane = {loc["name"]: loc["title"] for loc in dialog.selected_locations}
                self.editor_lokalizacje.set_data(nowe_lokalizacje_wybrane)
                # Natychmiastowy zapis ustawień
                self.save_settings(silent=True)
                messagebox.showinfo(
                    "Sukces",
                    f"✅ Pomyślnie zaimportowano i zapisano {len(nowe_lokalizacje_wybrane)} lokalizacji!"
                )
        finally:
            # Odblokuj scrollowanie rodzica
            self._parent_canvas.yview_scroll = original_yview_scroll
            self._scroll_blocked = False

    def _on_locations_error(self, error_msg: str):
        self.btn_detect_locations.configure(
            state="normal",
            text="🔍 Wykryj lokalizacje z GBP (pobierz listę automatycznie)"
        )
        messagebox.showerror("Błąd wykrywania lokalizacji", f"Nie udało się pobrać lokalizacji:\n\n{error_msg}")

    def rebuild_employee_editors(self):
        """
        Aktualizuje listę edytorów pracowników na dole ekranu na podstawie
        aktualnie wpisanych lokalizacji w edytorze powyżej.
        Zachowuje już istniejące edytory, by użytkownik nie stracił wpisanych danych.
        """
        if not hasattr(self, 'pracownicy_section_container') or not self.pracownicy_section_container.winfo_exists():
            return

        # Pobierz bieżący stan lokalizacji z edytora (słownik ID -> Nazwa)
        aktualne_lokalizacje = self.editor_lokalizacje.get_data()
        
        # Pobierz dotychczas zapisane dane z pliku konfiguracyjnego
        config = config_manager.load_config()
        zapisani_pracownicy = config.get("PRACOWNICY", {})
        
        # Najpierw zbierzmy to, co użytkownik aktualnie wpisał w edytorach na ekranie,
        # by nie stracić tych danych przy przebudowie.
        wpisane_dane = {}
        for loc_id, editor in list(self.location_employee_editors.items()):
            if editor.winfo_exists():
                wpisane_dane[loc_id] = editor.get_data()
            else:
                self.location_employee_editors.pop(loc_id, None)

        # 1. Usuń edytory dla lokalizacji, które zostały skasowane
        for loc_id in list(self.location_employee_editors.keys()):
            if loc_id not in aktualne_lokalizacje:
                editor_frame = self.location_employee_frames.pop(loc_id, None)
                if editor_frame and editor_frame.winfo_exists():
                    editor_frame.destroy()
                self.location_employee_editors.pop(loc_id, None)

        # 2. Utwórz/aktualizuj edytory dla lokalizacji
        for loc_id, custom_name in aktualne_lokalizacje.items():
            if loc_id not in self.location_employee_editors:
                # Utwórz ramkę-kartę dla danego edytora
                card = ctk.CTkFrame(self.pracownicy_section_container, corner_radius=10, fg_color="#262b30", height=10)
                card.pack(fill="x", pady=8, padx=5)
                
                # Ustal początkowe dane (z wpisanych, potem z pliku, na końcu puste)
                initial_list = []
                if isinstance(zapisani_pracownicy, dict):
                    initial_list = wpisane_dane.get(loc_id) or zapisani_pracownicy.get(loc_id) or []
                elif isinstance(zapisani_pracownicy, list) and not wpisane_dane.get(loc_id):
                    initial_list = zapisani_pracownicy
                
                editor = DynamicListEditor(
                    card, 
                    title=f"Klasyfikacja: Pracownicy dla '{custom_name}'",
                    val_placeholder="Pełne Imię i Nazwisko",
                    initial_list=initial_list
                )
                editor.pack(fill="both", expand=True, padx=10, pady=10)
                
                self.location_employee_editors[loc_id] = editor
                self.location_employee_frames[loc_id] = card
                
                # Przyśpieszenie scrollowania dla nowych elementów
                self._bind_fast_scroll(card)
            else:
                # Zaktualizuj tytuł edytora jeśli nazwa lokalizacji się zmieniła
                self.location_employee_editors[loc_id].configure_title(f"Klasyfikacja: Pracownicy dla '{custom_name}'")

    def _run_reclassification(self):
        # Najpierw zapisz aktualne ustawienia, żeby reklasyfikacja użyła nowych list pracowników/działów
        self.save_settings(silent=True)
        
        self.btn_reclassify.configure(state="disabled", text="⏳ Reklasyfikacja w toku...")
        
        def task():
            try:
                import api_manager
                count = api_manager.reklasyfikuj_baze_csv()
                self.after(0, lambda: messagebox.showinfo(
                    "Sukces",
                    f"✓ Pomyślnie zaktualizowano kategorie dla {count} opinii w bazie CSV!"
                ))
            except Exception as e:
                logger.exception("Błąd reklasyfikacji")
                self.after(0, lambda: messagebox.showerror("Błąd", f"Nie udało się zaktualizować bazy:\n\n{e}"))
            finally:
                self.after(0, lambda: self.btn_reclassify.configure(
                    state="normal", 
                    text="🔄 Reklasyfikuj istniejącą bazę (zastosuj nowe reguły do zapisanych opinii)"
                ))

        threading.Thread(target=task, daemon=True).start()

    # =========================================================================
    # Zapisz ustawienia
    # =========================================================================

    def save_settings(self, silent=False):
        new_pracownicy = {}
        for loc_id, editor in self.location_employee_editors.items():
            if editor.winfo_exists():
                new_pracownicy[loc_id] = editor.get_data()
        
        # Keep global fallback if it exists in config
        old_config = config_manager.load_config()
        old_pracownicy = old_config.get("PRACOWNICY", {})
        if isinstance(old_pracownicy, dict) and "global" in old_pracownicy:
            new_pracownicy["global"] = old_pracownicy["global"]

        new_config = {
            "GBP_CLIENT_SECRETS": self.entry_secrets.get().strip(),
            "GBP_TOKEN_FILE": self.entry_token.get().strip(),
            "NOTIFICATIONS_ENABLED": self.check_notifications_var.get(),
            "CSV_DATABASE": self.entry_csv.get().strip(),
            "EXCEL_FILE": self.entry_excel.get().strip(),
            "LOKALIZACJE": self.editor_lokalizacje.get_data(),
            "PRACOWNICY": new_pracownicy,
            "DZIALY": self.editor_dzialy.get_data()
        }

        config_manager.save_config(new_config)
        logger.info("Ustawienia GBP zapisane przez użytkownika")
        self._refresh_auth_status()
        
        if not silent:
            messagebox.showinfo("Zapisano", "Nowe ustawienia zostały pomyślnie zapisane i weszły w życie!")

    # --- Szybkie przewijanie (Fast scroll) ---
    def _bind_fast_scroll(self, widget):
        try:
            widget.bind("<MouseWheel>", self._on_fast_mousewheel)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_fast_scroll(child)

    def _on_fast_mousewheel(self, event):
        if getattr(self, "_scroll_blocked", False):
            return "break"
        if event.delta:
            # Domyślnie przewijanie w tkinter/customtkinter jest bardzo powolne na Windows.
            # Zwiększamy przewijanie o mnożnik 3x.
            amount = -1 * int(event.delta / 120) * 3
            self._parent_canvas.yview_scroll(amount, "units")
        return "break"
