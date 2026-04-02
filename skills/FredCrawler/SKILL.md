
---
Name: Access Fred API to obtain schema
Description: Obtaining good schema for Macro Analysis
---

## Target
Obtain a good data schema for Macro Analysis using the table format in /metadata/MACRO

## How to use
Create a file name FRED_MACRO.py in the metadata/ folder
Based on the series_id that can be found in the series_id.txt 
Use the Fred_API_KEY in the .env folder and for each series_id, access the observation data using: https://api.stlouisfed.org/fred/series/observations?series_id=[SERIES_ID]&api_key=[FRED_API_KEY]&file_type=json
crawl for main categories of each observation and store it using the similar format in /metadata/MACRO.py and save it in the FRED_MACRO.py
in the description categories of the table, making sure you are descriptive in the following format:
---
Name: \
Keywords \
Categories \
Use Cases: 
---

Any Abbreviation in the Name need to be fully written in the Keywords
Unit need to be specified for each category. If the Unit is unclear like "Index 1982-84=100", you need to include an explanation to it
---
## Example
description = """
Name: IMF Nominal GDP
Keywords: 
- International Money Fund
- Nominal
- Gross Domestic Products
Categories:
- Year
- GDP Nominal in USD
- GDP Growth in %
- GDP per Capita in USD
- Population Change in %
Use cases:
- MACRO analysis 
- Economy strength
"""
---

