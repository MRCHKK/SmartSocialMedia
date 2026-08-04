import customtkinter as ctk
from config_manager import get_employee_name, get_employee_department


class EmployeeListEditor(ctk.CTkFrame):
    def __init__(self, master, title, val_placeholder, initial_list, departments, **kwargs):
        if "height" not in kwargs:
            kwargs["height"] = 10
        super().__init__(master, **kwargs)
        self.rows = []
        self.departments = list(departments) if departments else ["SERWIS"]
        self.val_ph = val_placeholder

        # Tytuł sekcji
        self.title_label = ctk.CTkLabel(
            self, text=title,
            font=("Arial", 16, "bold"), text_color="#3a7ebf"
        )
        self.title_label.pack(pady=(12, 6))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=15, pady=5)

        for item in initial_list:
            self.add_row(item)

        btn_add = ctk.CTkButton(
            self, text="+ Dodaj nowego pracownika",
            command=lambda: self.add_row(""),
            width=200, height=34, font=("Arial", 13, "bold"),
            fg_color="#1f538d", hover_color="#14375e"
        )
        btn_add.pack(pady=(12, 15))

    def configure_title(self, new_title):
        if hasattr(self, 'title_label') and self.title_label.winfo_exists():
            self.title_label.configure(text=new_title)

    def update_departments(self, new_departments):
        """Aktualizuje listę dostępnych działów we wszystkich wierszach edytora."""
        self.departments = list(new_departments) if new_departments else ["SERWIS"]
        for _, entry_v, opt_dept in self.rows:
            if opt_dept.winfo_exists():
                current_val = opt_dept.get()
                opt_dept.configure(values=self.departments)
                if current_val in self.departments:
                    opt_dept.set(current_val)
                elif self.departments:
                    opt_dept.set(self.departments[0])

    def add_row(self, item_data):
        name = get_employee_name(item_data)
        dept = get_employee_department(item_data, default=self.departments[0] if self.departments else "SERWIS")

        if dept not in self.departments and self.departments:
            dept = self.departments[0]

        row = ctk.CTkFrame(self.container, fg_color="transparent")
        row.pack(fill="x", pady=4)

        entry_v = ctk.CTkEntry(
            row, height=32,
            placeholder_text=self.val_ph, font=("Arial", 13)
        )
        entry_v.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry_v.insert(0, name)

        # Wybierak Działu
        opt_dept = ctk.CTkOptionMenu(
            row, height=32, width=170,
            values=self.departments if self.departments else ["SERWIS"],
            font=("Arial", 12),
            dropdown_font=("Arial", 12)
        )
        opt_dept.set(dept)
        opt_dept.pack(side="left", padx=(0, 6))

        btn_del = ctk.CTkButton(
            row, text="✕", width=34, height=32,
            font=("Arial", 16, "bold"),
            fg_color="#c93434", hover_color="#9e2a2a",
            command=lambda f=row: self._remove_row(f)
        )
        btn_del.pack(side="right", padx=0)

        self.rows.append((row, entry_v, opt_dept))

    def _remove_row(self, row_frame):
        """Usuwa wiersz z listy i niszczy widget."""
        self.rows = [(r, v, d) for r, v, d in self.rows if r != row_frame]
        row_frame.destroy()

    def get_data(self):
        data = []
        for row, entry_v, opt_dept in self.rows:
            if row.winfo_exists():
                v = entry_v.get().strip()
                d = opt_dept.get().strip()
                if v:
                    data.append({
                        "imie_nazwisko": v,
                        "dzial": d
                    })
        return data
