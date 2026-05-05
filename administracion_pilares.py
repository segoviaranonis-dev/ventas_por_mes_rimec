import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd
from core.database import get_dataframe, commit_query, DBInspector

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AdminPilares(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NEXUS CORE | GESTIÓN ESTRATÉGICA DE PILARES")
        self.geometry("900x700")

        # --- Interfaz Chic ---
        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text="💎 ADMINISTRACIÓN DE PILARES Y VINCULACIÓN",
                                  font=ctk.CTkFont(size=22, weight="bold"))
        self.label.pack(pady=20)

        # Panel de Acciones
        self.action_frame = ctk.CTkFrame(self)
        self.action_frame.pack(fill="x", padx=20, pady=10)

        self.btn_check = ctk.CTkButton(self.action_frame, text="🔍 Auditar Blueprint Técnico",
                                      command=self.auditar, fg_color="#3498db")
        self.btn_check.pack(side="left", padx=10, pady=10)

        self.btn_excel = ctk.CTkButton(self.action_frame, text="📂 Cargar Excel (L+R+M+C)",
                                      command=self.cargar_excel, fg_color="#2ecc71", text_color="black")
        self.btn_excel.pack(side="left", padx=10, pady=10)

        # Consola de Eventos (Más grande para ver los datos)
        self.console = ctk.CTkTextbox(self, width=860, height=450, font=("Consolas", 12))
        self.console.pack(padx=20, pady=20)
        self.log("SISTEMA RIMEC ONLINE - Consola de Inspección Aritmética Lista.")

    def log(self, msg, level="INFO"):
        prefix = "✅" if level == "SUCCESS" else "❌" if level == "ERROR" else ">"
        self.console.insert("end", f"{prefix} {msg}\n")
        self.console.see("end")

    def auditar(self):
        self.log("INICIANDO INSPECCIÓN DE COMPONENTES DE PILARES...", "INFO")

        # 1. Auditoría de los 4 Pilares Físicos
        pilares = ["linea", "referencia", "material", "color"]
        for p in pilares:
            # SQL para ver los campos reales de la tabla
            query = f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{p}'
                ORDER BY ordinal_position;
            """
            df_cols = get_dataframe(query)

            if not df_cols.empty:
                cols_str = ", ".join([f"{row['column_name']} ({row['data_type']})" for _, row in df_cols.iterrows()])
                self.log(f"TABLA [{p.upper()}]: {cols_str}", "SUCCESS")
            else:
                self.log(f"TABLA [{p.upper()}]: No encontrada o sin columnas.", "ERROR")

        self.log("-" * 50)

        # 2. Auditoría de la Tabla de Relación (Vínculo L+R)
        vinculo_tabla = "linea_referencia_vinculo"
        query_v = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{vinculo_tabla}'"
        df_v = get_dataframe(query_v)

        if not df_v.empty:
            self.log(f"TABLA DE RELACIÓN [{vinculo_tabla.upper()}] DETECTADA.", "SUCCESS")
            for _, row in df_v.iterrows():
                self.log(f"   ↳ Campo: {row['column_name']} | Tipo: {row['data_type']}")
        else:
            self.log(f"TABLA DE RELACIÓN [{vinculo_tabla}]: Error Arquitectónico Crítico.", "ERROR")

    def cargar_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if path:
            self.log(f"Analizando archivo: {path}")
            # Lógica de procesamiento...
            self.log("Proyectando normalización aritmética de 14M USD...")

if __name__ == "__main__":
    app = AdminPilares()
    app.mainloop()