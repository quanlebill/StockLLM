from dataclasses import dataclass
from typing import Any
from .general_struct.struct import data as dt
from .general_struct.struct import Table

"""
This is Schema for GDP from Worldometer tables
"""
#Norminal GDP
@dataclass
class IMF_NOMINAL_GDP(Table):
    name = "IMF NOMINAL GDP"
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
    keywords = "Year, GDP_Nominal, GDP_Growth, GDP_per_capita, Population_Change, IMF_NOMINAL_GDP"
    Country = dt(dtype=str, unit=None)
    Year = dt(dtype=str, unit=None)
    GDP_Nominal = dt(dtype=float, unit="USD")
    GDP_Growth = dt(dtype=float, unit="%")
    GDP_Per_Capita = dt(dtype=float, unit="USD")
    Population_Change = dt(dtype=float, unit="%")

@dataclass
class IMF_PPP_GDP(Table):
    name = "IMF PPP GDP"
    description = """
    Name: IMF PPP GDP
    Keywords: 
    - International Money Fund
    - Purchasing Power Parity
    - Gross Domestic Products
    Categories:
    - Year
    - GDP PPP in USD
    - GDP PPP Growth in %
    - GDP PPP per Capita in USD
    - Population Change in %
    Use cases:
    - cases considering Power Purchasing Power Parity
    - MACRO analysis 
    - Economy strength
    """
    keywords = "Year, GDP_PPP, GDP_PPP_Per_Capita, GDP_PPP_Growth, Population_Change, IMF_PPP_GDP"
    Country = dt(dtype=str, unit=None)
    Year = dt(dtype=str, unit=None)
    GDP_PPP = dt(dtype=float, unit="USD")
    GDP_PPP_Per_Capita = dt(dtype=float, unit="USD")
    GDP_PPP_Growth = dt(dtype=float, unit="%")
    Population_Change = dt(dtype=float, unit="%")

@dataclass
class WB_GDP(Table):
    name = "WB GDP"
    description = """
    Name: WB GDP
    Keywords: 
    - World Bank
    - Gross Domestic Products
    Categories:
    - Year
    - GDP Nominal in USD
    - GDP Real (with constant, inflation adjusted) in USD
    - Population Change in %
    
    Use cases:
    - cases considering GDP value with World Bank
    - Adjusted Inflation GDP
    - MACRO analysis 
    - Economy strength
    """
    keywords = "Year, WB_GDP, GDP Nominal (Current USD), GDP REAL (Constant, Inflation, Adjusted), Population_Change"
    Country = dt(dtype=str, unit=None)
    Year = dt(dtype=str, unit=None)
    GDP_Nominal = dt(dtype=float, unit="USD")
    GDP_Real = dt(dtype=float, unit="USD")
    Population_Change = dt(dtype=float, unit="%")


"""

"""

