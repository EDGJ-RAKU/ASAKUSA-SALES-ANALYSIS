import duckdb

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "hotel_data.duckdb"

con = duckdb.connect(DB_FILE)

print(con.execute("SHOW TABLES").fetchdf())

con.close()