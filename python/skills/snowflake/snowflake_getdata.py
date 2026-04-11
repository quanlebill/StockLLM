import snowflake.connector
import json
from datetime import datetime, date
from decimal import Decimal
import re
import numpy as np

ACCOUNT  = "OJPHMJC-PB44708"
USER     = "QUANLE"
PASSWORD = "SFRuCyCo@2186887"
DATABASE = "STOCKLLM"
SCHEMA   = "RAW_DATA"
WAREHOUSE = "COMPUTE_WH"
DBT_SCHEMA = 'DBT_STOCK'


def get_table_metadata(cur: snowflake.connector.connection.SnowflakeConnection, query) -> list:
    #Get table columns name and data preview
    data = []

    cur.execute(query)

    #Handle Data type for json serializable
    for data_row in cur:
        data_row = list(data_row)
        for i in range(len(data_row)):
            if isinstance(data_row[i], datetime) or isinstance(data_row[i], date):
                data_row[i] = data_row[i].isoformat()
            elif isinstance(data_row[i], Decimal):
                data_row[i] = float(data_row[i])

        data.append(data_row)


    return data


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
    print(type(conn))
    print(f"Connected to {DATABASE}.{SCHEMA}\n")

    #Get all tables name
    import sys
    import os

    query = sys.argv[1]
    table_name = sys.argv[2]

    if not re.search("^--query=", query):
        raise Exception("Invalid query")
    if not re.search("^--table=", table_name):
        raise Exception("Invalid table")

    table_name = table_name[8:].upper()
    query = query[8:]
    data = get_table_metadata(cur, query)

    try:
        if sys.argv[3] == "--norm":
            data = np.array(data)
            col_means = np.mean(data, axis=0)
            col_stds = np.std(data, axis=0)
            data = (data - col_means)/(col_stds + 1e-5)

        data = data.tolist()
    except IndexError:
        print("normalize signal is wrong")

    #save to json
    with open(f"{os.getcwd()}/snowflake_getdata_response.json", "w") as f:
        json.dump({
            "table_name": table_name,
            "data": data,
        }, f, indent=4)
        f.close()



    conn.commit()
    cur.close()
    conn.close()
    print("\nDone.")
