"""
Upload FRED raw CSVs to Snowflake STOCKLLM.RAW_DATA
Table names are lowercase to match fred_sources.yml exactly (e.g. cpiaucsl, dff).
Table schema: COUNTRY VARCHAR, DATE VARCHAR, VALUE VARCHAR  (raw, no modification)
"""

import csv
import os
import snowflake.connector

ACCOUNT  = "OJPHMJC-PB44708"
USER     = "QUANLE"
PASSWORD = "SFRuCyCo@2186887"
DATABASE = "STOCKLLM"
SCHEMA   = "RAW_DATA"
WAREHOUSE = "COMPUTE_WH"

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")


def load_csv(series_id: str) -> tuple:
    path = os.path.join(RAW_DIR, series_id)
    rows = []
    schema = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        schema = list(reader.fieldnames)
        for row in reader:
            r = tuple(row[key] if row[key] != '' else None for key in schema)
            rows.append(r)
    return rows, schema


def upload_series(cursor, series_id: str) -> None:
    # Unquoted uppercase so Snowflake stores as uppercase — matches dbt source resolution
    table = series_id.upper().replace(".CSV", "").replace(" ", "_")
    rows, schemas = load_csv(series_id)

    col_defs = ", ".join(f'"{col}" VARCHAR' for col in schemas)
    cursor.execute(f'CREATE OR REPLACE TABLE "{table}" ({col_defs})')

    col_count = len(schemas)
    col_list = ", ".join(f'"{c}"' for c in schemas)
    placeholders = ", ".join(["%s" for _ in range(col_count)])
    cursor.executemany(
        f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
        rows,
    )
    print(f"  {table}: {len(rows)} rows uploaded")


if __name__ == "__main__":
    conn = snowflake.connector.connect(
        account=ACCOUNT,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
        schema=SCHEMA,
        warehouse=WAREHOUSE,
    )
    cur = conn.cursor()

    print(f"Connected to {DATABASE}.{SCHEMA}\n")

    for sid in os.listdir(RAW_DIR):
        try:
            upload_series(cur, sid)
        except Exception as e:
            print(f"  ERROR {sid}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("\nDone.")
