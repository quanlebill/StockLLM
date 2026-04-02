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

SERIES_IDS = [
    "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE",
    "PCETRIM12M159SFRBDAL", "MEDCPIM159SFRBCLE", "PPIACO",
    "FEDFUNDS", "DFF", "DFEDTARL", "DFEDTARU",
    "PAYEMS",
    "UMCSENT",
    "DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS30",
    "T10Y2Y", "T10Y3M",
]


def load_csv(series_id: str) -> list[tuple]:
    path = os.path.join(RAW_DIR, f"{series_id.lower()}.csv")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["country"], row["date"], row["value"]))
    return rows


def upload_series(cur, series_id: str) -> None:
    # Unquoted uppercase so Snowflake stores as uppercase — matches dbt source resolution
    table = series_id.upper()
    rows  = load_csv(series_id)

    cur.execute(f"""
        CREATE OR REPLACE TABLE {table} (
            country VARCHAR,
            date    VARCHAR,
            value   VARCHAR
        )
    """)

    cur.executemany(
        f"INSERT INTO {table} (country, date, value) VALUES (%s, %s, %s)",
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

    for sid in SERIES_IDS:
        try:
            upload_series(cur, sid)
        except Exception as e:
            print(f"  ERROR {sid}: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("\nDone.")
