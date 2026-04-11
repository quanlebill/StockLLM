"""
Snowflake I/O utility for model training scripts.
Provides fetch(table_name, query) -> pd.DataFrame,
consumed by train_gradient_boosting.py.
"""

import os
import sys
from datetime import datetime, date
from decimal import Decimal

import pandas as pd

# Resolve project root so mcp_snowflake is importable regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def fetch(table_name: str, query: str) -> pd.DataFrame:
    """
    Execute `query` against Snowflake and return results as a DataFrame.

    Args:
        table_name : Used only as a label in error messages.
        query      : Full SQL query to execute.

    Returns:
        pd.DataFrame with uppercase column names.
    """
    from python.skills.snowflake.mcp_snowflake import _connect

    conn = _connect()
    cur = conn.cursor()
    try:
        cur.execute(query)
        cols = [d[0].upper() for d in cur.description]
        rows = []
        for row in cur.fetchall():
            row = list(row)
            for i, v in enumerate(row):
                if isinstance(v, (datetime, date)):
                    row[i] = str(v)
                elif isinstance(v, Decimal):
                    row[i] = float(v)
            rows.append(row)
        return pd.DataFrame(rows, columns=cols)
    except Exception as exc:
        raise RuntimeError(f"snowflake_io.fetch failed on '{table_name}': {exc}") from exc
    finally:
        cur.close()
        conn.close()
