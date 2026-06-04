from pathlib import Path
import re

import duckdb
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"

excel_files = sorted(DATA_DIR.glob("*.xlsx"))
EXCEL_FILE = excel_files[-1]
DB_FILE = BASE_DIR / "hotel_data.duckdb"


def clean_table_name(name: str) -> str:
    name = re.sub(r"[^\w]+", "_", name)
    return name.strip("_").lower()


def clean_number(value):
    if pd.isna(value):
        return None

    value = str(value)
    value = (
        value.replace("¥", "")
        .replace(",", "")
        .replace("%", "")
        .strip()
    )

    if value == "" or value.lower() == "nan":
        return None

    try:
        return float(value)
    except Exception:
        return None


def save_raw_table(con, table_name: str, df: pd.DataFrame):
    df = df.copy()
    df.columns = [f"col_{i}" for i in range(len(df.columns))]
    df = df.astype(str)

    con.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    con.register("df_view", df)
    con.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM df_view')
    con.unregister("df_view")


def save_clean_table(con, table_name: str, df: pd.DataFrame):
    con.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    con.register("df_view", df)
    con.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM df_view')
    con.unregister("df_view")


def build_monthly_kpis(con):
    df = pd.read_excel(EXCEL_FILE, sheet_name="総表", header=None, dtype=str)

    metric_rows = {
        "sales": 3,
        "target": 4,
        "achievement_rate": 5,
        "total_guests": 6,
        "guest_nights": 7,
        "available_rooms": 8,
        "available_days": 9,
        "available_room_nights": 10,
        "sold_room_nights": 11,
        "occupancy_rate": 12,
        "adr": 13,
        "revpar": 14,
        "sqm_price_per_day": 15,
        "avg_guests": 16,
        "avg_stay_nights": 17,
    }

    # Oct 2025 → Sep 2026
    month_cols = [8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38, 41]

    rows = []

    for col in month_cols:
        month_value = df.iloc[2, col]

        if pd.isna(month_value):
            continue

        record = {"month": str(month_value)[:7]}

        for metric, row in metric_rows.items():
            try:
                record[metric] = clean_number(df.iloc[row, col])
            except Exception:
                record[metric] = None

        rows.append(record)

    save_clean_table(con, "monthly_kpis", pd.DataFrame(rows))


def build_ota_sales(con):
    df = pd.read_excel(EXCEL_FILE, sheet_name="総表", header=None, dtype=str)

    ota_rows = {
        "Airbnb": 20,
        "Booking.com": 21,
        "Agoda": 22,
        "Expedia": 23,
        "Trip.com": 24,
        "Jalan": 25,
        "Ikkyu": 26,
        "Direct / Own": 27,
    }

    # Oct 2025 → Sep 2026
    # If the source Excel has no OTA detail for future months,
    # values will appear as 0 / blank.
    month_cols = [8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38, 41]

    rows = []

    for col in month_cols:
        month_value = df.iloc[2, col]

        if pd.isna(month_value):
            continue

        month = str(month_value)[:7]

        for channel, row_num in ota_rows.items():
            try:
                sales = clean_number(df.iloc[row_num, col])
                booking_count = clean_number(df.iloc[row_num, col + 1])
                sales_share = clean_number(df.iloc[row_num, col + 2])
            except Exception:
                sales = None
                booking_count = None
                sales_share = None

            rows.append({
                "month": month,
                "channel": channel,
                "sales": sales,
                "booking_count": booking_count,
                "sales_share": sales_share,
            })

    save_clean_table(con, "monthly_ota_sales", pd.DataFrame(rows))


def import_excel_to_database():
    print("Starting Excel import...")

    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_FILE}")

    if DB_FILE.exists():
        DB_FILE.unlink()
        print("Deleted previous database.")

    xl = pd.ExcelFile(EXCEL_FILE)
    con = duckdb.connect(str(DB_FILE))

    metadata = []

    for sheet in xl.sheet_names:
        print(f"Importing sheet: {sheet}")

        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet, header=None, dtype=str)

        table_name = "raw_" + clean_table_name(sheet)
        save_raw_table(con, table_name, df)

        metadata.append({
            "sheet_name": sheet,
            "table_name": table_name,
            "rows": len(df),
            "columns": len(df.columns),
        })

    save_clean_table(con, "excel_sheets_metadata", pd.DataFrame(metadata))

    print("Building monthly_kpis...")
    build_monthly_kpis(con)

    print("Building monthly_ota_sales...")
    build_ota_sales(con)

    print("\nTables created:")
    print(con.execute("SHOW TABLES").fetchdf())

    con.close()

    print("\nDatabase successfully created:")
    print(DB_FILE)


if __name__ == "__main__":
    import_excel_to_database()