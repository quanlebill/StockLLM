"""
MCP Server for Snowflake — schema: dbt_stock
Tools:
  - get_mart_tables   : List MART_* tables with name, schema, and time range
  - save_conversation : Save selected tables/columns to CONVERSATION table, return key
"""

import json
import uuid
from datetime import datetime

import snowflake.connector
from mcp.server.fastmcp import FastMCP

ACCOUNT   = "OJPHMJC-PB44708"
USER      = "QUANLE"
PASSWORD  = "SFRuCyCo@2186887"
DATABASE  = "STOCKLLM"
SCHEMA    = "DBT_STOCK"
WAREHOUSE = "COMPUTE_WH"


def _connect():
    return snowflake.connector.connect(
        account=ACCOUNT,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
        schema=SCHEMA,
        warehouse=WAREHOUSE,
    )


mcp = FastMCP("snowflake-dbt-stock")


@mcp.tool()
def get_mart_tables() -> list:
    """
    Retrieve all tables starting with 'MART_' in the dbt_stock schema.
    Returns a list of dicts with: table_name, schema_name, and time_range
    (the min/max values of the first date/timestamp column found).
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT TABLE_NAME, TABLE_SCHEMA
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'DBT_STOCK'
          AND TABLE_NAME LIKE 'MART_%'
        ORDER BY TABLE_NAME
    """)
    tables = cur.fetchall()

    result = []
    for table_name, schema_name in tables:
        info = {"table_name": table_name, "schema_name": schema_name}

        # Find the first date/timestamp column
        try:
            cur.execute(f"""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'DBT_STOCK'
                  AND TABLE_NAME = '{table_name}'
                  AND (DATA_TYPE IN ('DATE', 'TIMESTAMP_NTZ', 'TIMESTAMP_LTZ', 'TIMESTAMP_TZ')
                       OR LOWER(COLUMN_NAME) LIKE '%date%'
                       OR LOWER(COLUMN_NAME) LIKE '%time%')
                ORDER BY ORDINAL_POSITION
                LIMIT 1
            """)
            date_col_row = cur.fetchone()

            if date_col_row:
                date_col = date_col_row[0]
                cur.execute(
                    f'SELECT MIN("{date_col}"), MAX("{date_col}") '
                    f'FROM {DATABASE}.{SCHEMA}.{table_name}'
                )
                min_d, max_d = cur.fetchone()
                info["time_range"] = {
                    "column": date_col,
                    "min": str(min_d) if min_d is not None else None,
                    "max": str(max_d) if max_d is not None else None,
                }
            else:
                info["time_range"] = None
        except Exception as e:
            info["time_range"] = {"error": str(e)}

        result.append(info)

    cur.close()
    conn.close()
    return result


@mcp.tool()
def save_conversation(table_name: list, column_name: dict) -> str:
    """
    Save a training configuration to the CONVERSATION table in Snowflake.

    Args:
        table_name  : List of table names selected for training.
        column_name : Dict mapping each table name to its list of selected column names.
                      Example: {"MART_WEEK_STOCK_VARIABLES": ["MA5", "RSI", "TRADE_TIMESTAMP"]}

    Returns:
        A UUID key string that can be used to retrieve this conversation later.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {DATABASE}.{SCHEMA}.CONVERSATION (
            KEY          VARCHAR        NOT NULL,
            CREATED_AT   TIMESTAMP_NTZ  NOT NULL,
            TABLE_NAMES  VARCHAR        NOT NULL,
            COLUMN_NAMES VARCHAR        NOT NULL
        )
    """)

    key = str(uuid.uuid4())
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

    cur.execute(
        f"""INSERT INTO {DATABASE}.{SCHEMA}.CONVERSATION
               (KEY, CREATED_AT, TABLE_NAMES, COLUMN_NAMES)
            VALUES (%s, TO_TIMESTAMP_NTZ(%s), %s, %s)""",
        (key, now_str, json.dumps(table_name), json.dumps(column_name)),
    )

    conn.commit()
    cur.close()
    conn.close()
    return key


if __name__ == "__main__":
    mcp.run()
