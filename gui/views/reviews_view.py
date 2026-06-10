import customtkinter as ctk
import pandas as pd
import os
import datetime
from tkinter import ttk

import config_manager

class ReviewsView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="transparent")
        
        os.makedirs("data", exist_ok=True)
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # --- HEADER / SEARCH BAR ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(
            header_frame, text="🔎 Wewnętrzna Baza Opinii", 
            font=("Arial", 20, "bold")
        ).pack(side="left")

        self.search_entry = ctk.CTkEntry(
            header_frame, placeholder_text="Szukaj po treści / autorze...", 
            width=250, height=35
        )
        self.search_entry.pack(side="right", padx=(10, 0))
        self.search_entry.bind("<KeyRelease>", self._filter_data)

        btn_reload = ctk.CTkButton(
            header_frame, text="Zaktualizuj widok", width=120, height=35,
            fg_color="#444", hover_color="#333",
            command=self.load_data
        )
        btn_reload.pack(side="right")

        # --- DATA GRID (TREEVIEW) ---
        style = ttk.Style()
        style.theme_use("default")
        
        # Dark mode styling dla Treeview
        style.configure(
            "Treeview", 
            background="#2b2b2b", foreground="#e0e0e0", 
            rowheight=30, fieldbackground="#2b2b2b",
            borderwidth=0, bordercolor="#1e1e1e"
        )
        style.configure("Treeview.Heading", background="#1e1e1e", foreground="#ffffff", font=("Arial", 11, "bold"), borderwidth=0)
        style.map("Treeview", background=[('selected', '#3a7ebf')])
        style.map("Treeview.Heading", background=[('active', '#333')])

        grid_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        grid_wrapper.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        columns = ("Lokalizacja", "Autor", "Ocena", "Data", "Kategoria", "ReviewID")
        self.tree = ttk.Treeview(grid_wrapper, columns=columns, show="headings", selectmode="browse")
        
        # Konfiguracja kolumn
        for col in columns:
            self.tree.heading(col, text=col)
            
        self.tree.column("Lokalizacja", width=120)
        self.tree.column("Autor", width=140)
        self.tree.column("Ocena", width=50, anchor="center")
        self.tree.column("Data", width=110)
        self.tree.column("Kategoria", width=120)
        # Ukryta kolumna ID do celów technicznych
        self.tree.column("ReviewID", width=0, stretch=False)
        self.tree.heading("ReviewID", text="")

        # Scrollbar dla tabeli (nowoczesny, ciemny CTkScrollbar)
        scrollbar = ctk.CTkScrollbar(grid_wrapper, orientation="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill="both", expand=True)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # --- PANEL SZCZEGÓŁÓW NA DOLE ---
        self.details_frame = ctk.CTkFrame(self, fg_color="#1f2226", corner_radius=10, height=200)
        self.details_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.details_frame.grid_propagate(False)
        self.details_frame.grid_columnconfigure(0, weight=1)
        self.details_frame.grid_rowconfigure(1, weight=1)
        
        # Tresc opinii
        ctk.CTkLabel(self.details_frame, text="Treść opinii klienta:", text_color="#5cbaf0", font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        self.txt_tresc = ctk.CTkTextbox(self.details_frame, fg_color="#181a1d", text_color="#ccc")
        self.txt_tresc.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Stan danych
        self.df = None
        self.df_filtered = None
        self.current_selected_review = None

    def load_data(self):
        config = config_manager.load_config()
        db_path = config.get("CSV_DATABASE", "database_opinie.csv")
        
        if not os.path.exists(db_path):
            self._display_message("Brak pliku z bazą opinii (CSV). Pobierz opinie z Google by go zbudować.")
            return

        try:
            self.df = pd.read_csv(db_path)
            # Obsluga starych wersji
            if 'ReviewID' not in self.df.columns:
                self.df['ReviewID'] = ''
                
            # Sortowanie po dacie (od najnowszych)
            self.df['Data_dt'] = pd.to_datetime(self.df['Data'], format="%d.%m.%Y %H:%M", errors='coerce')
            self.df = self.df.sort_values(by='Data_dt', ascending=False)
            self.df = self.df.drop(columns=['Data_dt'])

            self.df_filtered = self.df.copy()
            self._render_tree(self.df_filtered)
            self._clear_details()
        except Exception as e:
            self._display_message(f"Błąd odczytu bazy: {e}")

    def _render_tree(self, df):
        self.tree.delete(*self.tree.get_children())
        if df is None or df.empty:
            return
            
        for idx, row in df.iterrows():
            # Skracamy gwiazdki wizualnie
            ocena = f"{str(row.get('Ocena', ''))} ⭐"
            values = (
                str(row.get('Lokalizacja', '')),
                str(row.get('Autor', '')),
                ocena,
                str(row.get('Data', '')),
                str(row.get('Kategoria', '')),
                str(row.get('ReviewID', ''))
            )
            self.tree.insert("", "end", iid=str(idx), values=values)

    def _filter_data(self, event=None):
        if self.df is None: return
        query = self.search_entry.get().lower().strip()
        
        if not query:
            self.df_filtered = self.df.copy()
        else:
            self.df_filtered = self.df[
                self.df['Tresc'].astype(str).str.lower().str.contains(query, na=False) |
                self.df['Autor'].astype(str).str.lower().str.contains(query, na=False) |
                self.df['Kategoria'].astype(str).str.lower().str.contains(query, na=False)
            ]
        self._render_tree(self.df_filtered)

    def _on_select(self, event):
        selected = self.tree.selection()
        if not selected:
            self._clear_details()
            return

        iid = selected[0]
        try:
            row_idx = int(iid)
            self.current_selected_review = self.df.loc[row_idx].to_dict()
            tresc = str(self.current_selected_review.get('Tresc', 'Brak treści'))
            
            self.txt_tresc.configure(state="normal")
            self.txt_tresc.delete("1.0", "end")
            self.txt_tresc.insert("end", tresc)
            self.txt_tresc.configure(state="disabled")
        except Exception as e:
            logger.error(f"Błąd podczas wybierania opinii z DataFrame: {e}")

    def _clear_details(self):
        self.current_selected_review = None
        
        self.txt_tresc.configure(state="normal")
        self.txt_tresc.delete("1.0", "end")
        self.txt_tresc.configure(state="disabled")

    def _display_message(self, msg):
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", values=(msg, "", "", "", "", ""))
