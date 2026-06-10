import customtkinter as ctk

class DynamicDictEditor(ctk.CTkFrame):
    def __init__(self, master, title, key_placeholder, val_placeholder, initial_dict, is_list=False, on_change_callback=None, **kwargs):
        if "height" not in kwargs:
            kwargs["height"] = 10
        super().__init__(master, **kwargs)
        self.is_list = is_list
        self.on_change_callback = on_change_callback
        self.rows = []

        # Tytuł sekcji (bardziej czytelny, z ładnym kolorem)
        ctk.CTkLabel(
            self, text=title, 
            font=("Arial", 16, "bold"), text_color="#3a7ebf"
        ).pack(pady=(12, 6))
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=15, pady=5)

        self.key_ph = key_placeholder
        self.val_ph = val_placeholder

        for k, v in initial_dict.items():
            v_str = ", ".join(v) if is_list else v
            self.add_row(k, v_str, silent=True)

        btn_add = ctk.CTkButton(
            self, text="+ Dodaj nową pozycję",
            command=lambda: self.add_row("", ""),
            width=180, height=34, font=("Arial", 13, "bold"),
            fg_color="#1f538d", hover_color="#14375e"
        )
        btn_add.pack(pady=(12, 15))

    def _trigger_callback(self):
        if self.on_change_callback:
            self.on_change_callback()

    def add_row(self, key_text, val_text, silent=False):
        row = ctk.CTkFrame(self.container, fg_color="transparent")
        row.pack(fill="x", pady=4)

        entry_k = ctk.CTkEntry(
            row, width=240, height=32, 
            placeholder_text=self.key_ph, font=("Arial", 13)
        )
        entry_k.pack(side="left", padx=(0, 6))
        entry_k.insert(0, key_text)
        entry_k.bind("<FocusOut>", lambda e: self._trigger_callback())

        entry_v = ctk.CTkEntry(
            row, height=32,
            placeholder_text=self.val_ph, font=("Arial", 13)
        )
        entry_v.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry_v.insert(0, val_text)
        entry_v.bind("<FocusOut>", lambda e: self._trigger_callback())

        btn_del = ctk.CTkButton(
            row, text="✕", width=34, height=32, 
            font=("Arial", 16, "bold"),
            fg_color="#c93434", hover_color="#9e2a2a",
            command=lambda f=row: self._remove_row(f)
        )
        btn_del.pack(side="right", padx=0)

        self.rows.append((row, entry_k, entry_v))
        if not silent:
            self._trigger_callback()

    def _remove_row(self, row_frame):
        """Usuwa wiersz z listy i niszczy widget — zapobiega memory leak."""
        self.rows = [(r, k, v) for r, k, v in self.rows if r != row_frame]
        row_frame.destroy()
        self._trigger_callback()

    def set_data(self, new_dict: dict):
        """Zastępuje wszystkie wiersze nowym słownikiem (używane przy auto-wykrywaniu lokalizacji)."""
        # Usuń wszystkie istniejące wiersze
        for row, _, _ in self.rows:
            if row.winfo_exists():
                row.destroy()
        self.rows = []
        # Dodaj nowe
        for k, v in new_dict.items():
            v_str = ", ".join(v) if self.is_list else v
            self.add_row(k, v_str, silent=True)
        self._trigger_callback()

    def get_data(self):
        data = {}
        for row, entry_k, entry_v in self.rows:
            if row.winfo_exists():
                k = entry_k.get().strip()
                v = entry_v.get().strip()
                if k:
                    if self.is_list:
                        data[k] = [item.strip() for item in v.split(",") if item.strip()]
                    else:
                        data[k] = v
        return data
