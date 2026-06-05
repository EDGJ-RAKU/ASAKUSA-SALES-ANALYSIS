from pathlib import Path

import re

import duckdb

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "Data"

# Automatically use latest Excel file in Data folder

excel_files = sorted(DATA_DIR.glob("*.xlsx"))

if not excel_files:

    raise FileNotFoundError(f"No Excel file found in {DATA_DIR}")

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

    month_cols = [8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38, 41]

    rows = []

    for col in month_cols:

        month_value = df.iloc[2, col]

        if pd.isna(month_value):

            continue

        month = str(month_value)[:7]

        for channel, row_num in ota_rows.items():

            rows.append({

                "month": month,

                "channel": channel,

                "sales": clean_number(df.iloc[row_num, col]),

                "booking_count": clean_number(df.iloc[row_num, col + 1]),

                "sales_share": clean_number(df.iloc[row_num, col + 2]),

            })

    save_clean_table(con, "monthly_ota_sales", pd.DataFrame(rows))

def extract_month_from_sheet(sheet_name: str):

    match = re.search(r"(20\d{2})年\s*([0-9０-９]+)月", sheet_name)

    if not match:

        return None

    year = match.group(1)

    month = match.group(2)

    trans = str.maketrans("０１２３４５６７８９", "0123456789")

    month = month.translate(trans)

    return f"{year}-{int(month):02d}"

def build_reservations(con):
    xl = pd.ExcelFile(EXCEL_FILE)
    all_rows = []

    def clean_header(x):
        if pd.isna(x):
            return ""
        return str(x).strip().replace("\n", "").replace(" ", "")

    for sheet in xl.sheet_names:
        if "予約一覧表" not in sheet:
            continue

        print(f"Building reservations from: {sheet}")

        raw = pd.read_excel(
            EXCEL_FILE,
            sheet_name=sheet,
            header=None,
            dtype=str
        )

        header_row = None

        for i in range(min(10, len(raw))):
            row_values = [clean_header(v) for v in raw.iloc[i].tolist()]

            if "チェックイン日" in row_values and "チェックアウト日" in row_values:
                header_row = i
                break

        if header_row is None:
            print(f"WARNING: Could not find reservation header in sheet: {sheet}")
            continue

        headers = [clean_header(v) for v in raw.iloc[header_row].tolist()]

        df = raw.iloc[header_row + 1:].copy()
        df.columns = headers
        df = df.dropna(how="all")

        rename_map = {
            "予約番号": "booking_id",
            "チェックイン日": "checkin_date",
            "チェックアウト日": "checkout_date",
            "予約日": "booking_date",
            "申込日": "booking_date",
            "泊数": "nights",

            "予約サイト": "channel",
            "予約サイト名称": "channel",

            "部屋タイプ名称": "room_type",
            "室数": "rooms",

            "ゲスト名": "guest_name",
            "宿泊者氏名": "guest_name",

            "国・地域": "country_region",

            "大人": "adults",
            "大人人数": "adults",
            "大人人数計": "adults",

            "子供": "children",
            "子供人数": "children",

            "予約合計額": "gross_booking_amount",
            "OTAサービス料": "ota_service_fee",
            "サービス料": "service_fee",
            "クレジットカード手数料": "card_fee",
            "サイド別銀行入金小計": "site_bank_deposit",
            "サイト別銀行入金小計": "site_bank_deposit",
            "銀行入金小計": "bank_deposit",
            "受取金": "received_amount",
            "入金日": "deposit_date",
            "ポイント割引額": "points_discount",
            "ポイント額": "points_discount",
            "決済方法": "payment_method",
            "泊延べ日数": "guest_nights",
            "宿泊延べ日数": "guest_nights",
        }

        df = df.rename(columns=rename_map)

        if "checkin_date" not in df.columns:
            print(f"WARNING: checkin_date missing after rename in sheet: {sheet}")
            continue

        if "country_region" not in df.columns:
            print(f"INFO: No country_region column in sheet: {sheet}; skipping nationality analysis for this sheet.")
            continue

        keep_cols = [
            "booking_id",
            "checkin_date",
            "checkout_date",
            "booking_date",
            "nights",
            "channel",
            "room_type",
            "rooms",
            "guest_name",
            "country_region",
            "adults",
            "children",
            "gross_booking_amount",
            "ota_service_fee",
            "received_amount",
            "service_fee",
            "card_fee",
            "site_bank_deposit",
            "bank_deposit",
            "deposit_date",
            "points_discount",
            "payment_method",
            "guest_nights",
        ]

        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols].copy()

        # If received_amount does not exist, use bank_deposit or gross amount as fallback
        if "received_amount" not in df.columns:
            if "bank_deposit" in df.columns:
                df["received_amount"] = df["bank_deposit"]
            elif "site_bank_deposit" in df.columns:
                df["received_amount"] = df["site_bank_deposit"]
            elif "gross_booking_amount" in df.columns:
                df["received_amount"] = df["gross_booking_amount"]
            else:
                df["received_amount"] = 0

        for col in [
            "gross_booking_amount",
            "ota_service_fee",
            "received_amount",
            "service_fee",
            "card_fee",
            "site_bank_deposit",
            "bank_deposit",
            "points_discount",
            "nights",
            "rooms",
            "adults",
            "children",
            "guest_nights",
        ]:
            if col in df.columns:
                df[col] = df[col].apply(clean_number)

        for col in ["checkin_date", "checkout_date", "booking_date", "deposit_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        country_map = {

            "アメリカ": "America",

            "米国": "America",

            "オーストラリア": "Australia",

            "カナダ": "Canada",

            "フランス": "France",

            "イギリス": "United Kingdom",

            "英国": "United Kingdom",

            "台湾": "Taiwan",

            "韓国": "South Korea",

            "香港": "Hong Kong",

            "中国": "China",

            "シンガポール": "Singapore",

            "フィリピン": "Philippines",

            "タイ": "Thailand",

            "日本": "Japan",

        }

        country_map = {
            "アメリカ": "America",
            "米国": "America",
            "オーストラリア": "Australia",
            "カナダ": "Canada",
            "フランス": "France",
            "イギリス": "United Kingdom",
            "英国": "United Kingdom",
            "台湾": "Taiwan",
            "韓国": "South Korea",
            "香港": "Hong Kong",
            "中国": "China",
            "シンガポール": "Singapore",
            "フィリピン": "Philippines",
            "タイ": "Thailand",
            "日本": "Japan",
            "イスラエル": "Israel",
            "ロシア": "Russia",
            "ポーランド": "Poland",
            "マレーシア": "Malaysia",
            "イタリア": "Italy",
            "ドイツ": "Germany",
            "ペルー": "Peru",
            "オランダ": "Netherlands",
            "ルクセンブルク": "Luxembourg",
            "スペイン": "Spain",
            "ブータン": "Bhutan",
        }

        df["country_region"] = df["country_region"].fillna("Unknown")
        df["country_region"] = df["country_region"].replace("", "Unknown")
        df["country_region"] = df["country_region"].replace(country_map)

        df["source_sheet"] = sheet
        df["month"] = df["checkin_date"].dt.strftime("%Y-%m")

        all_rows.append(df)

    if all_rows:
        reservations = pd.concat(all_rows, ignore_index=True)
    else:
        reservations = pd.DataFrame()

    save_clean_table(con, "reservations", reservations)

def import_excel_to_database():

    print("Starting Excel import...")

    print(f"Using Excel file: {EXCEL_FILE}")

    if DB_FILE.exists():

        DB_FILE.unlink()

        print("Deleted previous database.")

    xl = pd.ExcelFile(EXCEL_FILE)

    con = duckdb.connect(str(DB_FILE))

    metadata = []

    for sheet in xl.sheet_names:

        print(f"Importing raw sheet: {sheet}")

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

    print("Building reservations...")

    build_reservations(con)

    print("\nTables created:")

    print(con.execute("SHOW TABLES").fetchdf())

    con.close()

    print("\nDatabase successfully created:")

    print(DB_FILE)

if __name__ == "__main__":

    import_excel_to_database()