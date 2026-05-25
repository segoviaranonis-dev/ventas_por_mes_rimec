import pandas as pd
from pathlib import Path

XLSX_PATH = Path("f9 30-03.xlsx")
df = pd.read_excel(XLSX_PATH, sheet_name="23956332")
print("Unique Pedido_proveedor values in sheet:")
print(df["Pedido_proveedor"].dropna().unique().tolist())
