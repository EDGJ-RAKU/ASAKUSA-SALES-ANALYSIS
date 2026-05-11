# debug_ota.py

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"

EXCEL_FILE = DATA_DIR / "2025_10_2026_03_data.xlsx"

df = pd.read_excel(
    EXCEL_FILE,
    sheet_name="総表",
    header=None,
    dtype=str
)

# Print rows around OTA section
for i in range(10, 30):

    values = []

    for j in range(0, 15):
        values.append(str(df.iloc[i, j]))

    print(f"\nROW {i}")
    print(values)