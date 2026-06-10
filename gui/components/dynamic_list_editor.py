import customtkinter as ctk

class DynamicListEditor(ctk.CTkFrame):
    def __init__(self, master, title, val_placeholder, initial_list, **kwargs):
        if "height" not in kwargs:
            kwargs["height"] = 10
        super().__init__(master, **kwargs)
        self.rows = []

        # Tytuł sekcji (bardziej czytelny, z ładnym kolorem)
        self.title_label = ctk.CTkLabel(
            self, text=title, 
            font=("Arial", 16, "bold"), text_color="#3a7ebf"
        )
        self.title_label.pack(pady=(12, 6))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=15, pady=5)

        self.val_ph = val_placeholder

        for item in initial_list:
            self.add_row(item)

        btn_add = ctk.CTkButton(
            self, text="+ Dodaj nową pozycję",
            command=lambda: self.add_row(""),
            width=180, height=34, font=("Arial", 13, "bold"),
            fg_color="#1f538d", hover_color="#14375e"
        )
        btn_add.pack(pady=(12, 15))

    def configure_title(self, new_title):
        if hasattr(self, 'title_label') and self.title_label.winfo_exists():
            self.title_label.configure(text=new_title)

    def add_row(self, val_text):
        row = ctk.CTkFrame(self.container, fg_color="transparent")
        row.pack(fill="x", pady=4)

        entry_v = ctk.CTkEntry(
            row, height=32,
            placeholder_text=self.val_ph, font=("Arial", 13)
        )
        entry_v.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry_v.insert(0, val_text)

        btn_del = ctk.CTkButton(
            row, text="✕", width=34, height=32, 
            font=("Arial", 16, "bold"),
            fg_color="#c93434", hover_color="#9e2a2a",
            command=lambda f=row: self._remove_row(f)
        )
        btn_del.pack(side="right", padx=0)

        self.rows.append((row, entry_v))

    def _remove_row(self, row_frame):
        """Usuwa wiersz z listy i niszczy widget — zapobiega memory leak."""
        self.rows = [(r, v) for r, v in self.rows if r != row_frame]
        row_frame.destroy()

    def get_data(self):
        data = []
        for row, entry_v in self.rows:
            if row.winfo_exists():
                v = entry_v.get().strip()
                if v:
                    data.append(v)
        return data
