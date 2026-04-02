# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
StockLLM is a Python project (configured via PyCharm/IntelliJ with a virtual environment named `StockLLM`)

## Constraints
- Do NOT self correct any skill , 
- Do NOT access or read files outside of this repository directory (`D:\Personals\StockLLM`).


## Creating skill
- base on the list of important variable listed in `baseknowledge/stock_prediction_variables_1week.md` I want you to review the table in the file
- for every missing data: I want you to use the provided MCP AlphaVantage OR Yfinance to write the python file to retrieve them
- data retrieve will be store in data/raw, csv file
- name of csv file must be short but descriptive, dont use abbreviation or short name
- save python file to skills/Extraction as your skill to pull this data
- there will be data that can be calculated from other. I want you to note that down as a markdown file for me.

## Important
- Your jobs is only write program to pull this data and list all variable that can calculated from retrieved data based on given listed 
- do not modified the data, keep it the way it is when you retrieve
- name file must be short but meaning full. do not "DSGM1" write it all out: "1_Month_Treasury_Yield"