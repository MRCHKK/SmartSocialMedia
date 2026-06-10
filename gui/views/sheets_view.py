# gui/views/sheets_view.py
import customtkinter as ctk
import os
import glob
import subprocess
import platform
import threading
import logging
import datetime
import threading
import logging
from tkcalendar import Calendar

import excel_manager

logger = logging.getLogger(__name__)


class SheetsView(ctk.CTkFrame):
    def __init__(self, master, app_root, **kwargs):
        super().__init__(master, **kwargs)
        self.app_root = app_root
        self.configure(fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=340)
        self.grid_rowconfigure(0, weight=1)

        # LEWY PANEL — generowanie arkuszy
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        # PRAWY PANEL — gotowe pliki
        self.right_panel = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        self.right_panel.grid(row=0, column=1, sticky="nsew")

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        # Nagłówek
        ctk.CTkLabel(
            self.left_panel,
            text="📊 Generowanie Arkuszy Excel",
            font=("Arial", 20, "bold"), anchor="w"
        ).pack(fill="x", pady=(0, 20))

        # Karta: Suche dane
        card = ctk.CTkFrame(self.left_panel, fg_color="#1e2a1e", corner_radius=10)
        card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            card,
            text="📄 Raport",
            font=("Arial", 15, "bold"), text_color="#4caf82", anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 4))

        ctk.CTkLabel(
            card,
            text="Eksport wszystkich recenzji z bazy CSV do arkusza Excel.\nZawiera: lokalizację, autora, ocenę, datę, kategorię i treść.",
            font=("Arial", 12), text_color="#aaaaaa", anchor="w", justify="left"
        ).pack(fill="x", padx=15, pady=(0, 12))

        # Oblicz poprzedni miesiąc do domyślnych wartości
        now = datetime.datetime.now()
        first_current = now.replace(day=1)
        last_prev = first_current - datetime.timedelta(days=1)
        first_prev = last_prev.replace(day=1)

        # Zakres dat
        ctk.CTkLabel(card, text="Zakres danych (DD.MM.YYYY):", font=("Arial", 12), text_color="#aaaaaa").pack(anchor="w", padx=15, pady=(0, 5))
        
        dates_frame = ctk.CTkFrame(card, fg_color="transparent")
        dates_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(dates_frame, text="Od:", font=("Arial", 12)).pack(side="left")
        
        self.date_from = ctk.CTkEntry(dates_frame, width=100, placeholder_text="DD.MM.YYYY")
        self.date_from.pack(side="left", padx=(5, 5))
        self.date_from.insert(0, first_prev.strftime("%d.%m.%Y"))
        
        btn_cal_from = ctk.CTkButton(dates_frame, text="📅", width=30, fg_color="#333", hover_color="#444", 
                                     command=lambda: self._open_calendar(self.date_from, first_prev))
        btn_cal_from.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(dates_frame, text="Do:", font=("Arial", 12)).pack(side="left")
        
        self.date_to = ctk.CTkEntry(dates_frame, width=100, placeholder_text="DD.MM.YYYY")
        self.date_to.pack(side="left", padx=(5, 5))
        self.date_to.insert(0, last_prev.strftime("%d.%m.%Y"))
        
        btn_cal_to = ctk.CTkButton(dates_frame, text="📅", width=30, fg_color="#333", hover_color="#444", 
                                   command=lambda: self._open_calendar(self.date_to, last_prev))
        btn_cal_to.pack(side="left", padx=(0, 0))

        self.all_dates_var = ctk.BooleanVar(value=True)
        self.chk_all_dates = ctk.CTkCheckBox(
            card, text="Pobierz wszystkie opinie (ignoruj daty)", 
            variable=self.all_dates_var, font=("Arial", 12),
            command=self._toggle_dates
        )
        self.chk_all_dates.pack(anchor="w", padx=15, pady=(0, 15))

        self.btn_generuj = ctk.CTkButton(
            card,
            text="📊 Generuj Excel",
            font=("Arial", 14, "bold"), height=46, corner_radius=8,
            fg_color="#226e45", hover_color="#174d30",
            command=self.run_excel
        )
        self.btn_generuj.pack(fill="x", padx=15, pady=(0, 15))

        # Pasek postępu (ukryty domyślnie)
        self.progress_bar = ctk.CTkProgressBar(card, height=8, corner_radius=4)
        self.progress_bar.configure(mode="indeterminate", progress_color="#226e45")

        # Status / log output
        log_wrapper = ctk.CTkFrame(self.left_panel, fg_color="#1e1e1e", corner_radius=10)
        log_wrapper.pack(fill="both", expand=True, pady=(12, 0))

        ctk.CTkLabel(
            log_wrapper, text="📋 Log operacji",
            font=("Arial", 13, "bold"), text_color="#888888", anchor="w"
        ).pack(fill="x", padx=12, pady=(10, 4))

        self.log_box = ctk.CTkTextbox(
            log_wrapper, fg_color="#141618", text_color="#cccccc",
            font=("Consolas", 12), state="disabled"
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._toggle_dates()

    def _build_right_panel(self):
        header_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            header_frame, text="📁 Gotowe pliki",
            font=("Arial", 18, "bold")
        ).pack(side="left")

        ctk.CTkButton(
            header_frame, text="Odśwież", width=80, height=28,
            corner_radius=6, fg_color="#444444", hover_color="#333333",
            command=self.refresh_files
        ).pack(side="right")

        self.files_scroll = ctk.CTkScrollableFrame(self.right_panel, fg_color="transparent")
        self.files_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 10))

    # -------------------------------------------------------------------------
    # Logika

    def _open_calendar(self, entry_widget, initial_date):
        top = ctk.CTkToplevel(self)
        top.title("Wybierz datę")
        top.geometry("300x260")
        top.attributes('-topmost', True)
        top.grab_set()

        cal = Calendar(top, selectmode='day', date_pattern='dd.mm.yyyy', locale='pl_PL',
                       background='#1e1e1e', foreground='white',
                       headersbackground='#2b2b2b', headersforeground='white',
                       selectbackground='#3a7ebf', selectforeground='white',
                       bordercolor='#555555', normalbackground='#1e1e1e',
                       normalforeground='white', weekendbackground='#2a2a2a',
                       weekendforeground='#ff6b6b', othermonthforeground='#555',
                       othermonthbackground='#1e1e1e', othermonthweforeground='#555',
                       othermonthwebackground='#2a2a2a')
        cal.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        
        try:
            # Spróbuj ustawić datę na tę z pola
            current_date_str = entry_widget.get()
            if current_date_str:
                d = datetime.datetime.strptime(current_date_str, "%d.%m.%Y")
                cal.selection_set(d.date())
            else:
                cal.selection_set(initial_date.date())
        except Exception:
            cal.selection_set(initial_date.date())
        
        def on_select():
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, cal.get_date())
            top.destroy()
            
        ctk.CTkButton(top, text="✔ Wybierz", command=on_select, fg_color="#226e45", hover_color="#174d30").pack(pady=(0, 10))

    def _toggle_dates(self):
        state = "disabled" if self.all_dates_var.get() else "normal"
        self.date_from.configure(state=state)
        self.date_to.configure(state=state)

    def _log(self, msg: str):
        """Dopisuje linię do logu operacji."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _toggle_loading_state(self, show: bool):
        if show:
            self.btn_generuj.configure(state="disabled", text="⏳ Generowanie...")
            self.progress_bar.pack(fill="x", padx=15, pady=(0, 15))
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.btn_generuj.configure(state="normal", text="📊 Generuj Excel")



    def run_excel(self):
        if self.all_dates_var.get():
            date_range = None
            log_txt = "wszystkie opinie"
        else:
            d_from = self.date_from.get().strip()
            d_to = self.date_to.get().strip()
            date_range = (d_from, d_to)
            log_txt = f"od {d_from} do {d_to}"

        self._log(f"--- Generowanie arkusza Excel ({log_txt}) ---")
        self._toggle_loading_state(True)
        
        def task():
            try:
                excel_manager.przenies_do_excel(False, date_range=date_range)
                self.app_root.after(0, lambda: self._log("✅ Arkusz wygenerowany pomyślnie!"))
                self.app_root.after(500, self.refresh_files)
            except Exception as e:
                logger.exception("Błąd podczas generowania Excel")
                err_msg = str(e)
                self.app_root.after(0, lambda msg=err_msg: self._log(f"❌ BŁĄD: {msg}"))
            finally:
                self.app_root.after(0, lambda: self._toggle_loading_state(False))
                
        threading.Thread(target=task, daemon=True).start()

    def refresh_files(self):
        for widget in self.files_scroll.winfo_children():
            widget.destroy()

        files_xls = glob.glob(os.path.join("raporty", "*.xlsx"))
        files = files_xls
        files += glob.glob("*.xlsx")
        files = list(set(files))
        files.sort(key=os.path.getmtime, reverse=True)

        if not files:
            ctk.CTkLabel(
                self.files_scroll,
                text="Brak wygenerowanych\nplików w folderach.",
                text_color="#777777"
            ).pack(pady=40)
            return

        for f in files:
            is_excel = f.endswith(".xlsx")
            card_color = "#324436" if is_excel else "#353f4a"

            card = ctk.CTkFrame(self.files_scroll, fg_color=card_color, corner_radius=8)
            card.pack(fill="x", pady=4, padx=5)

            icon = "📊" if is_excel else "📄"
            f_display = os.path.basename(f)
            ctk.CTkLabel(
                card, text=f"{icon} {f_display}",
                font=("Consolas", 12, "bold"), anchor="w"
            ).pack(side="top", fill="x", padx=10, pady=(8, 4))

            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(side="bottom", fill="x", padx=10, pady=(0, 8))

            ctk.CTkButton(
                btn_box, text="Otwórz", width=80, height=26, corner_radius=4,
                font=("Arial", 12, "bold"),
                fg_color="#555555", hover_color="#2e7d32" if is_excel else "#1565c0",
                command=lambda path=f: self._open_file(path)
            ).pack(side="left", expand=True, padx=(0, 4))

            ctk.CTkButton(
                btn_box, text="W folderze", width=80, height=26, corner_radius=4,
                font=("Arial", 12),
                fg_color="#555555", hover_color="#757575",
                command=lambda path=f: self._open_folder(path)
            ).pack(side="left", expand=True, padx=(4, 0))

    def _open_file(self, filepath):
        try:
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.call(["open", filepath])
            else:
                subprocess.call(["xdg-open", filepath])
        except Exception as e:
            self._log(f"[Błąd] Nie udało się otworzyć pliku: {e}")

    def _open_folder(self, filepath):
        try:
            abs_path = os.path.abspath(filepath)
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{abs_path}"')
            elif platform.system() == "Darwin":
                subprocess.call(["open", "-R", abs_path])
            else:
                subprocess.call(["xdg-open", os.path.dirname(abs_path)])
        except Exception as e:
            self._log(f"[Błąd] Nie udało się otworzyć folderu: {e}")
