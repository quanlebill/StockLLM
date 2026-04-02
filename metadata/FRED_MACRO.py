from dataclasses import dataclass
from typing import Any
from .general_struct.struct import data as dt
from .general_struct.struct import Table

"""
Schema for FRED (Federal Reserve Economic Data) Macro Analysis tables.
Series metadata verified via FRED API on 2026-03-22.
"""

# ── GDP / OUTPUT ──────────────────────────────────────────────────────────────

@dataclass
class FRED_REAL_GDP(Table):
    name = "FRED Real GDP"
    description = """
    Name: FRED Real Gross Domestic Product
    Keywords:
    - Federal Reserve Economic Data
    - Real Gross Domestic Product
    - Bureau of Economic Analysis
    - Chained 2017 Dollars (inflation-adjusted using 2017 as the base year; chain-weighting removes substitution bias)
    - Quarterly
    Categories:
    - Date: quarter start date (YYYY-MM-DD)
    - Real_GDP_Level: inflation-adjusted total economic output in Billions of Chained 2017 Dollars
    - Real_GDP_QoQ_Growth: quarter-over-quarter percent change in real GDP
    Use Cases:
    - Business cycle dating (expansion vs recession)
    - Economic output benchmarking across time
    - Input to output gap calculation
    FRED Series: GDPC1 | Quarterly | BEA | Jan 1947 - present
    """
    keywords = "Date, Real_GDP_Level, Real_GDP_QoQ_Growth, GDPC1, A191RL1Q225SBEA, BEA, GDP, real output, chained dollars"
    Date                = dt(dtype=str,   unit=None)
    Real_GDP_Level      = dt(dtype=float, unit="Billions of Chained 2017 Dollars")
    Real_GDP_QoQ_Growth = dt(dtype=float, unit="%")


@dataclass
class FRED_POTENTIAL_GDP(Table):
    name = "FRED Potential GDP"
    description = """
    Name: FRED Real Potential Gross Domestic Product
    Keywords:
    - Federal Reserve Economic Data
    - Congressional Budget Office
    - Real Potential Gross Domestic Product
    - Chained 2017 Dollars (inflation-adjusted using 2017 as the base year)
    - Output Gap (difference between actual GDP and potential GDP as a percent of potential)
    - Quarterly
    Categories:
    - Date: quarter start date (YYYY-MM-DD)
    - Potential_GDP: CBO estimate of maximum sustainable non-inflationary output in Billions of Chained 2017 Dollars
    - Output_Gap: (Real GDP minus Potential GDP) / Potential GDP * 100 in % (negative = slack, positive = overheating)
    Use Cases:
    - Identifying recession slack (output gap below 0) vs overheating (output gap above 0)
    - Fed policy calibration against the neutral rate
    - Long-run growth trend analysis
    FRED Series: GDPPOT | Quarterly | CBO | Jan 1949 - Oct 2036 (includes projections)
    """
    keywords = "Date, Potential_GDP, Output_Gap, GDPPOT, CBO, Congressional Budget Office, potential output, output gap"
    Date          = dt(dtype=str,   unit=None)
    Potential_GDP = dt(dtype=float, unit="Billions of Chained 2017 Dollars")
    Output_Gap    = dt(dtype=float, unit="%")


# ── INFLATION ─────────────────────────────────────────────────────────────────

@dataclass
class FRED_CPI(Table):
    name = "FRED CPI Headline"
    description = """
    Name: FRED Consumer Price Index - All Urban Consumers (Headline)
    Keywords:
    - Federal Reserve Economic Data
    - Consumer Price Index
    - Bureau of Labor Statistics
    - All Urban Consumers
    - Seasonally Adjusted
    - Index 1982-1984=100 (price level expressed relative to average prices in the 1982-1984 base period, set to 100)
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - CPI_Level: price index level in Index 1982-1984=100
    - CPI_YoY: year-over-year percent change (annual headline inflation rate)
    - CPI_MoM: month-over-month percent change (monthly headline inflation rate)
    Use Cases:
    - Measuring headline consumer price inflation
    - Cost-of-living adjustments for Social Security, wages, and TIPS bonds
    - Comparing price levels across time periods
    FRED Series: CPIAUCSL | Monthly | BLS | Jan 1947 - present
    """
    keywords = "Date, CPI_Level, CPI_YoY, CPI_MoM, CPIAUCSL, BLS, consumer price index, headline inflation, urban consumers"
    Date      = dt(dtype=str,   unit=None)
    CPI_Level = dt(dtype=float, unit="Index 1982-1984=100")
    CPI_YoY   = dt(dtype=float, unit="%")
    CPI_MoM   = dt(dtype=float, unit="%")


@dataclass
class FRED_CORE_CPI(Table):
    name = "FRED Core CPI"
    description = """
    Name: FRED Core Consumer Price Index - All Items Less Food and Energy
    Keywords:
    - Federal Reserve Economic Data
    - Core Consumer Price Index
    - Bureau of Labor Statistics
    - All Items Less Food and Energy (food and energy excluded because their prices are volatile and distort the underlying trend)
    - Seasonally Adjusted
    - Index 1982-1984=100 (price level expressed relative to average prices in the 1982-1984 base period, set to 100)
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Core_CPI_Level: core price index level in Index 1982-1984=100
    - Core_CPI_YoY: year-over-year percent change (core annual inflation rate)
    - Core_CPI_MoM: month-over-month percent change (core monthly inflation rate)
    Use Cases:
    - Fed monetary policy assessment independent of energy/food supply shocks
    - Measuring persistent underlying inflation trend
    - Medium-term inflation forecasting
    FRED Series: CPILFESL | Monthly | BLS | Jan 1957 - present
    """
    keywords = "Date, Core_CPI_Level, Core_CPI_YoY, Core_CPI_MoM, CPILFESL, BLS, core CPI, core inflation, less food energy"
    Date           = dt(dtype=str,   unit=None)
    Core_CPI_Level = dt(dtype=float, unit="Index 1982-1984=100")
    Core_CPI_YoY   = dt(dtype=float, unit="%")
    Core_CPI_MoM   = dt(dtype=float, unit="%")


@dataclass
class FRED_PCE(Table):
    name = "FRED PCE Headline"
    description = """
    Name: FRED Personal Consumption Expenditures Chain-type Price Index (Headline)
    Keywords:
    - Federal Reserve Economic Data
    - Personal Consumption Expenditures
    - Bureau of Economic Analysis
    - Chain-type Price Index (adjusts for consumer substitution between goods as prices change)
    - Seasonally Adjusted
    - Index 2017=100 (price level expressed relative to 2017 average prices, set to 100)
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - PCE_Level: price index level in Index 2017=100
    - PCE_YoY: year-over-year percent change (annual PCE inflation rate)
    - PCE_MoM: month-over-month percent change (monthly PCE inflation rate)
    Use Cases:
    - Fed primary inflation gauge; broader basket than CPI
    - Federal Open Market Committee meeting analysis
    - Cross-checking CPI inflation signals
    FRED Series: PCEPI | Monthly | BEA | Jan 1959 - present
    """
    keywords = "Date, PCE_Level, PCE_YoY, PCE_MoM, PCEPI, BEA, personal consumption expenditures, PCE inflation, Federal Reserve"
    Date      = dt(dtype=str,   unit=None)
    PCE_Level = dt(dtype=float, unit="Index 2017=100")
    PCE_YoY   = dt(dtype=float, unit="%")
    PCE_MoM   = dt(dtype=float, unit="%")


@dataclass
class FRED_CORE_PCE(Table):
    name = "FRED Core PCE"
    description = """
    Name: FRED Personal Consumption Expenditures Excluding Food and Energy (Core PCE)
    Keywords:
    - Federal Reserve Economic Data
    - Core Personal Consumption Expenditures
    - Bureau of Economic Analysis
    - Excluding Food and Energy (removes volatile categories to reveal persistent inflation)
    - Chain-type Price Index
    - Seasonally Adjusted
    - Index 2017=100 (price level expressed relative to 2017 average prices, set to 100)
    - Federal Open Market Committee 2 percent inflation target benchmark
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Core_PCE_Level: core price index level in Index 2017=100
    - Core_PCE_YoY: year-over-year percent change; Fed compares this directly against its 2% target
    - Core_PCE_MoM: month-over-month percent change
    Use Cases:
    - Direct benchmark against the Fed 2% price stability mandate
    - Federal Open Market Committee rate hike or cut decision analysis
    - Most watched inflation series for monetary policy forecasting
    FRED Series: PCEPILFE | Monthly | BEA | Jan 1959 - present
    """
    keywords = "Date, Core_PCE_Level, Core_PCE_YoY, Core_PCE_MoM, PCEPILFE, BEA, core PCE, Fed target, FOMC, 2 percent target"
    Date           = dt(dtype=str,   unit=None)
    Core_PCE_Level = dt(dtype=float, unit="Index 2017=100")
    Core_PCE_YoY   = dt(dtype=float, unit="%")
    Core_PCE_MoM   = dt(dtype=float, unit="%")


@dataclass
class FRED_TRIMMED_MEAN_PCE(Table):
    name = "FRED Trimmed Mean PCE"
    description = """
    Name: FRED Trimmed Mean Personal Consumption Expenditures Inflation Rate
    Keywords:
    - Federal Reserve Economic Data
    - Federal Reserve Bank of Dallas
    - Trimmed Mean PCE (each month the highest and lowest price-change components are removed before averaging)
    - Percent Change from Year Ago
    - Underlying inflation trend
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Trimmed_Mean_PCE_YoY: 12-month trimmed mean PCE inflation rate in %
    Use Cases:
    - Identifying underlying inflation trend free of outliers in both directions
    - Comparing against Core PCE to detect distortions from extreme price movers
    - Real-time signal of where inflation is sustainably headed
    FRED Series: PCETRIM12M159SFRBDAL | Monthly | Dallas Fed | Jan 1978 - present
    """
    keywords = "Date, Trimmed_Mean_PCE_YoY, PCETRIM12M159SFRBDAL, Dallas Fed, trimmed mean, underlying inflation, PCE"
    Date                 = dt(dtype=str,   unit=None)
    Trimmed_Mean_PCE_YoY = dt(dtype=float, unit="%")


@dataclass
class FRED_MEDIAN_CPI(Table):
    name = "FRED Median CPI"
    description = """
    Name: FRED Median Consumer Price Index
    Keywords:
    - Federal Reserve Economic Data
    - Federal Reserve Bank of Cleveland
    - Median Consumer Price Index (inflation rate of the middle-ranked CPI expenditure category each month)
    - Percent Change from Year Ago
    - Robust to outliers
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Median_CPI_YoY: year-over-year percent change of the median CPI component in %
    Use Cases:
    - Cross-checking Core CPI and PCE for distortion from a small number of large price swings
    - Measuring the central tendency of consumer price changes
    - Detecting broad-based vs narrow inflation
    FRED Series: MEDCPIM159SFRBCLE | Monthly | Cleveland Fed | Dec 1983 - present
    """
    keywords = "Date, Median_CPI_YoY, MEDCPIM159SFRBCLE, Cleveland Fed, median CPI, underlying inflation, outlier-robust"
    Date           = dt(dtype=str,   unit=None)
    Median_CPI_YoY = dt(dtype=float, unit="%")


@dataclass
class FRED_PPI(Table):
    name = "FRED PPI All Commodities"
    description = """
    Name: FRED Producer Price Index by Commodity - All Commodities
    Keywords:
    - Federal Reserve Economic Data
    - Producer Price Index
    - Bureau of Labor Statistics
    - All Commodities
    - Not Seasonally Adjusted
    - Index 1982=100 (price level expressed relative to 1982 average prices, set to 100)
    - Upstream pricing pressure from producers before costs reach consumers
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - PPI_Level: producer price index level in Index 1982=100
    - PPI_YoY: year-over-year percent change in PPI
    - PPI_MoM: month-over-month percent change in PPI
    Use Cases:
    - Leading indicator for future consumer inflation via cost pass-through to CPI
    - Supply chain pricing pressure analysis
    - Corporate profit margin analysis
    FRED Series: PPIACO | Monthly | BLS | Jan 1913 - present
    """
    keywords = "Date, PPI_Level, PPI_YoY, PPI_MoM, PPIACO, BLS, producer price index, pipeline inflation, commodity prices"
    Date      = dt(dtype=str,   unit=None)
    PPI_Level = dt(dtype=float, unit="Index 1982=100")
    PPI_YoY   = dt(dtype=float, unit="%")
    PPI_MoM   = dt(dtype=float, unit="%")


# ── INTEREST RATES ────────────────────────────────────────────────────────────

@dataclass
class FRED_FED_FUNDS_MONTHLY(Table):
    name = "FRED Federal Funds Rate Monthly"
    description = """
    Name: FRED Federal Funds Effective Rate (Monthly)
    Keywords:
    - Federal Reserve Economic Data
    - Federal Funds Effective Rate
    - Federal Reserve
    - Federal Open Market Committee
    - Overnight interbank lending rate (the rate banks charge each other for overnight reserve loans)
    - Primary monetary policy instrument
    - Not Seasonally Adjusted
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Fed_Funds_Rate: monthly average effective federal funds rate in %
    Use Cases:
    - Tracking the Fed monetary policy stance across cycles
    - Correlation analysis with inflation, unemployment, and asset prices
    - Business cycle phase identification
    FRED Series: FEDFUNDS | Monthly | Federal Reserve | Jul 1954 - present
    """
    keywords = "Date, Fed_Funds_Rate, FEDFUNDS, Federal Reserve, FOMC, Federal Open Market Committee, overnight rate, monetary policy"
    Date           = dt(dtype=str,   unit=None)
    Fed_Funds_Rate = dt(dtype=float, unit="%")


@dataclass
class FRED_FED_FUNDS_DAILY(Table):
    name = "FRED Federal Funds Rate Daily"
    description = """
    Name: FRED Federal Funds Effective Rate (Daily)
    Keywords:
    - Federal Reserve Economic Data
    - Federal Funds Effective Rate
    - Federal Reserve
    - Daily 7-Day rate
    - Overnight interbank lending rate
    - Not Seasonally Adjusted
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - Fed_Funds_Rate: daily effective federal funds rate in %
    Use Cases:
    - Real-time monitoring of policy rate transmission
    - Detecting deviations from the Federal Open Market Committee target range
    - High-frequency macro strategy signals
    FRED Series: DFF | Daily 7-Day | Federal Reserve | Jul 1954 - present
    """
    keywords = "Date, Fed_Funds_Rate, DFF, Federal Reserve, daily, overnight rate, monetary policy"
    Date           = dt(dtype=str,   unit=None)
    Fed_Funds_Rate = dt(dtype=float, unit="%")


@dataclass
class FRED_FED_FUNDS_TARGET(Table):
    name = "FRED Federal Funds Target Range"
    description = """
    Name: FRED Federal Funds Target Range - Lower and Upper Limit
    Keywords:
    - Federal Reserve Economic Data
    - Federal Open Market Committee
    - Federal Funds Target Range
    - Lower Limit (the floor of the policy rate corridor set by the Federal Open Market Committee)
    - Upper Limit (the ceiling of the policy rate corridor set by the Federal Open Market Committee)
    - Rate corridor (the band within which the effective overnight rate must trade)
    - Not Seasonally Adjusted
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - Target_Lower: Federal Open Market Committee lower bound of the target corridor in %
    - Target_Upper: Federal Open Market Committee upper bound of the target corridor in %
    Use Cases:
    - Identifying Federal Open Market Committee rate hike or cut dates and magnitude
    - Mapping policy tightening and easing cycles
    - Measuring deviation of the effective rate from the target
    FRED Series: DFEDTARL / DFEDTARU | Daily | Federal Reserve | Dec 2008 - present
    """
    keywords = "Date, Target_Lower, Target_Upper, DFEDTARL, DFEDTARU, FOMC, Federal Open Market Committee, target rate, rate corridor"
    Date         = dt(dtype=str,   unit=None)
    Target_Lower = dt(dtype=float, unit="%")
    Target_Upper = dt(dtype=float, unit="%")


@dataclass
class FRED_TREASURY_YIELD_CURVE(Table):
    name = "FRED Treasury Yield Curve"
    description = """
    Name: FRED U.S. Treasury Yield Curve - Constant Maturity Rates
    Keywords:
    - Federal Reserve Economic Data
    - U.S. Treasury Securities
    - Constant Maturity (yield interpolated to a fixed maturity regardless of the actual remaining term of any specific bond)
    - Investment Basis (annualized yield assuming the bond is held to maturity)
    - Not Seasonally Adjusted
    - Yield Curve (the plot of Treasury yields from short to long maturities)
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - Y1M: 1-Month Treasury yield in % (DGS1MO, available from Jul 2001)
    - Y3M: 3-Month Treasury yield in % (DGS3MO, available from Sep 1981)
    - Y6M: 6-Month Treasury yield in % (DGS6MO, available from Sep 1981)
    - Y1: 1-Year Treasury yield in % (DGS1, available from Jan 1962)
    - Y2: 2-Year Treasury yield in % (DGS2, available from Jun 1976)
    - Y5: 5-Year Treasury yield in % (DGS5, available from Jan 1962)
    - Y10: 10-Year Treasury yield in % (DGS10, available from Jan 1962); global risk-free rate benchmark
    - Y30: 30-Year Treasury yield in % (DGS30, available from Feb 1977)
    Use Cases:
    - Yield curve shape analysis (normal, inverted, or flat)
    - Discounting future cash flows in equity and bond valuation
    - Term premium and inflation expectations decomposition
    FRED Series: DGS1MO, DGS3MO, DGS6MO, DGS1, DGS2, DGS5, DGS10, DGS30 | Daily | U.S. Treasury
    """
    keywords = "Date, Y1M, Y3M, Y6M, Y1, Y2, Y5, Y10, Y30, DGS, Treasury, yield curve, constant maturity, risk-free rate"
    Date = dt(dtype=str,   unit=None)
    Y1M  = dt(dtype=float, unit="%")
    Y3M  = dt(dtype=float, unit="%")
    Y6M  = dt(dtype=float, unit="%")
    Y1   = dt(dtype=float, unit="%")
    Y2   = dt(dtype=float, unit="%")
    Y5   = dt(dtype=float, unit="%")
    Y10  = dt(dtype=float, unit="%")
    Y30  = dt(dtype=float, unit="%")


@dataclass
class FRED_YIELD_CURVE_SPREADS(Table):
    name = "FRED Yield Curve Spreads"
    description = """
    Name: FRED Treasury Yield Curve Spreads - Recession Indicators
    Keywords:
    - Federal Reserve Economic Data
    - Yield Curve Spread (the difference in yield between two Treasury maturities)
    - 10-Year Minus 2-Year Treasury Spread (T10Y2Y)
    - 10-Year Minus 3-Month Treasury Spread (T10Y3M); preferred input for the New York Fed recession probability model
    - Yield Curve Inversion (spread below 0 means short-term rates exceed long-term rates; historically precedes recessions)
    - Not Seasonally Adjusted
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - Spread_10Y_2Y: 10-year yield minus 2-year yield in % (negative = inverted curve)
    - Spread_10Y_3M: 10-year yield minus 3-month yield in % (negative = inverted curve)
    Use Cases:
    - Recession probability forecasting (New York Fed model uses T10Y3M)
    - Monetary policy tightness assessment
    - Risk-on / risk-off macro regime positioning
    FRED Series: T10Y2Y (from Jun 1976), T10Y3M (from Jan 1982) | Daily | Federal Reserve
    """
    keywords = "Date, Spread_10Y_2Y, Spread_10Y_3M, T10Y2Y, T10Y3M, yield inversion, recession signal, term spread"
    Date          = dt(dtype=str,   unit=None)
    Spread_10Y_2Y = dt(dtype=float, unit="%")
    Spread_10Y_3M = dt(dtype=float, unit="%")


@dataclass
class FRED_SOFR(Table):
    name = "FRED SOFR"
    description = """
    Name: FRED Secured Overnight Financing Rate
    Keywords:
    - Federal Reserve Economic Data
    - Secured Overnight Financing Rate
    - Federal Reserve Bank of New York
    - Replaced USD London Interbank Offered Rate (LIBOR) as the primary U.S. dollar benchmark rate
    - Overnight repo rate (loan secured by U.S. Treasury collateral, settled overnight)
    - Risk-free rate benchmark for dollar-denominated derivatives and floating-rate instruments
    - Not Seasonally Adjusted
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - SOFR_Rate: daily Secured Overnight Financing Rate in %
    Use Cases:
    - Pricing floating-rate loans, interest rate derivatives, and securitizations post-LIBOR transition
    - Tracking overnight funding market conditions
    - Spread versus Fed Funds as a financial stress indicator
    FRED Series: SOFR | Daily | New York Fed | Apr 2018 - present
    """
    keywords = "Date, SOFR_Rate, SOFR, Secured Overnight Financing Rate, New York Fed, overnight, repo, LIBOR replacement, benchmark rate"
    Date      = dt(dtype=str,   unit=None)
    SOFR_Rate = dt(dtype=float, unit="%")


@dataclass
class FRED_PRIME_RATE(Table):
    name = "FRED Bank Prime Rate"
    description = """
    Name: FRED Bank Prime Loan Rate
    Keywords:
    - Federal Reserve Economic Data
    - Bank Prime Loan Rate
    - Federal Reserve
    - Base lending rate set by commercial banks for their most creditworthy customers
    - Typically Federal Funds Rate plus 300 basis points (3 percentage points above the fed funds rate)
    - Benchmark for consumer credit products including credit cards and home equity lines of credit
    - Event-based (only updated when the rate changes, not on a fixed schedule)
    Categories:
    - Date: date of each rate change (YYYY-MM-DD)
    - Prime_Rate: bank prime lending rate in %
    Use Cases:
    - Consumer credit cost analysis for credit cards, auto loans, and home equity lines of credit
    - Transmission of Fed policy to household borrowing costs
    - Historical lending rate comparisons
    FRED Series: PRIME | Event-based | Federal Reserve | Aug 1955 - present
    """
    keywords = "Date, Prime_Rate, PRIME, bank prime loan rate, Federal Reserve, lending rate, consumer credit, HELOC, credit cards, basis points"
    Date       = dt(dtype=str,   unit=None)
    Prime_Rate = dt(dtype=float, unit="%")


@dataclass
class FRED_MORTGAGE_RATE_30Y(Table):
    name = "FRED 30-Year Mortgage Rate"
    description = """
    Name: FRED 30-Year Fixed Rate Mortgage Average - United States
    Keywords:
    - Federal Reserve Economic Data
    - Freddie Mac Primary Mortgage Market Survey
    - 30-Year Fixed Rate Mortgage
    - Weekly average reported each Thursday
    - Housing affordability
    - Transmission of Federal Reserve monetary policy to the housing market
    - Weekly
    Categories:
    - Date: Thursday of each week (YYYY-MM-DD)
    - Mortgage_Rate_30Y: national average 30-year fixed mortgage rate in %
    Use Cases:
    - Housing affordability and demand forecasting
    - Measuring Fed policy pass-through to consumer borrowing costs
    - Homebuilder and real estate sector analysis
    FRED Series: MORTGAGE30US | Weekly Thursday | Freddie Mac | Apr 1971 - present
    """
    keywords = "Date, Mortgage_Rate_30Y, MORTGAGE30US, Freddie Mac, 30-year fixed rate mortgage, housing, affordability"
    Date              = dt(dtype=str,   unit=None)
    Mortgage_Rate_30Y = dt(dtype=float, unit="%")


# ── EMPLOYMENT / LABOR MARKET ─────────────────────────────────────────────────

@dataclass
class FRED_UNEMPLOYMENT_RATE(Table):
    name = "FRED Unemployment Rate U-3"
    description = """
    Name: FRED Unemployment Rate - U-3 Headline
    Keywords:
    - Federal Reserve Economic Data
    - Unemployment Rate
    - Bureau of Labor Statistics
    - U-3 (official headline unemployment measure; persons unemployed as a percent of the civilian labor force)
    - Current Population Survey (monthly household survey used to measure labor force status)
    - Seasonally Adjusted
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Unemployment_Rate: U-3 unemployment rate in %
    Use Cases:
    - Primary labor market health gauge
    - Fed dual mandate tracking (maximum employment alongside price stability)
    - Recession identification via the Sahm Rule (triggers when rate rises 0.5% from 12-month low)
    FRED Series: UNRATE | Monthly | BLS | Jan 1948 - present
    """
    keywords = "Date, Unemployment_Rate, UNRATE, BLS, Bureau of Labor Statistics, U-3, unemployment, jobless rate, dual mandate"
    Date              = dt(dtype=str,   unit=None)
    Unemployment_Rate = dt(dtype=float, unit="%")


@dataclass
class FRED_U6_RATE(Table):
    name = "FRED U-6 Broad Unemployment Rate"
    description = """
    Name: FRED U-6 Unemployment Rate - Total Unemployed Plus Marginally Attached Plus Part-Time for Economic Reasons
    Keywords:
    - Federal Reserve Economic Data
    - U-6 Unemployment Rate (broadest official measure of labor underutilization)
    - Bureau of Labor Statistics
    - Marginally Attached Workers (persons who want work but stopped actively searching in the past 4 weeks)
    - Part-Time for Economic Reasons (persons who want full-time work but can only find part-time positions)
    - Seasonally Adjusted
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - U6_Rate: broad underutilization rate in % (includes unemployed, discouraged, and underemployed workers)
    Use Cases:
    - Full labor slack measurement beyond the headline U-3 rate
    - Identifying hidden unemployment during recoveries
    - Wage pressure analysis; tight U-6 leads to wage acceleration
    FRED Series: U6RATE | Monthly | BLS | Jan 1994 - present
    """
    keywords = "Date, U6_Rate, U6RATE, BLS, U-6, underemployment, labor slack, discouraged workers, marginally attached, part-time economic reasons"
    Date    = dt(dtype=str,   unit=None)
    U6_Rate = dt(dtype=float, unit="%")


@dataclass
class FRED_NONFARM_PAYROLLS(Table):
    name = "FRED Nonfarm Payrolls"
    description = """
    Name: FRED All Employees - Total Nonfarm Payrolls
    Keywords:
    - Federal Reserve Economic Data
    - Nonfarm Payrolls
    - Bureau of Labor Statistics
    - Establishment Survey (Current Employment Statistics; counts filled jobs not individual persons)
    - Seasonally Adjusted
    - Thousands of Persons
    - Most closely watched number in the monthly Employment Situation report
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Payrolls_Level: total nonfarm employees in Thousands of Persons
    - Payrolls_MoM_Change: month-over-month change in total nonfarm payrolls in Thousands of Persons
    Use Cases:
    - Headline jobs report analysis; most market-moving labor data release
    - Labor demand cycle tracking across expansions and recessions
    - Recession onset and recovery confirmation
    FRED Series: PAYEMS | Monthly | BLS | Jan 1939 - present
    """
    keywords = "Date, Payrolls_Level, Payrolls_MoM_Change, PAYEMS, BLS, nonfarm payrolls, jobs report, employment, establishment survey"
    Date                = dt(dtype=str,   unit=None)
    Payrolls_Level      = dt(dtype=float, unit="Thousands of Persons")
    Payrolls_MoM_Change = dt(dtype=float, unit="Thousands of Persons")


@dataclass
class FRED_LABOR_FORCE_PARTICIPATION(Table):
    name = "FRED Labor Force Participation Rate"
    description = """
    Name: FRED Labor Force Participation Rate
    Keywords:
    - Federal Reserve Economic Data
    - Labor Force Participation Rate
    - Bureau of Labor Statistics
    - Current Population Survey
    - Civilian Noninstitutional Population (all persons aged 16 and over not in the military or institutional settings)
    - Seasonally Adjusted
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - LFPR: share of the civilian noninstitutional population that is either employed or actively seeking work in %
    Use Cases:
    - Measuring the supply side of the labor market
    - Demographics-adjusted labor slack analysis
    - Distinguishing structural from cyclical changes in unemployment
    FRED Series: CIVPART | Monthly | BLS | Jan 1948 - present
    """
    keywords = "Date, LFPR, CIVPART, BLS, labor force participation rate, labor supply, civilian noninstitutional population, workforce"
    Date = dt(dtype=str,   unit=None)
    LFPR = dt(dtype=float, unit="%")


@dataclass
class FRED_JOB_OPENINGS(Table):
    name = "FRED Job Openings JOLTS"
    description = """
    Name: FRED Job Openings - Total Nonfarm (JOLTS)
    Keywords:
    - Federal Reserve Economic Data
    - Job Openings and Labor Turnover Survey (JOLTS)
    - Bureau of Labor Statistics
    - Job Openings (unfilled positions that employers are actively recruiting for on the survey reference date)
    - Labor demand imbalance
    - Seasonally Adjusted
    - Level in Thousands
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Job_Openings: total nonfarm job openings in Thousands
    - Openings_to_Unemployed_Ratio: job openings divided by number of unemployed persons as a Ratio (above 1.0 means more open jobs than unemployed workers)
    Use Cases:
    - Labor market tightness assessment; high ratio signals wage pressure
    - Fed assessment of the maximum employment mandate
    - Leading indicator for future hiring and payroll growth
    FRED Series: JTSJOL | Monthly | BLS | Dec 2000 - present
    """
    keywords = "Date, Job_Openings, Openings_to_Unemployed_Ratio, JTSJOL, BLS, JOLTS, Job Openings and Labor Turnover Survey, labor tightness, vacancies"
    Date                         = dt(dtype=str,   unit=None)
    Job_Openings                 = dt(dtype=float, unit="Thousands")
    Openings_to_Unemployed_Ratio = dt(dtype=float, unit="Ratio")


# ── MONEY SUPPLY ──────────────────────────────────────────────────────────────

@dataclass
class FRED_M2(Table):
    name = "FRED M2 Money Supply"
    description = """
    Name: FRED M2 Money Supply (Weekly)
    Keywords:
    - Federal Reserve Economic Data
    - M2 Money Supply (broad money aggregate)
    - Federal Reserve
    - M2 Components: M1 (physical currency plus demand deposits) plus savings accounts, money market mutual funds, and small time deposits
    - Billions of Dollars (nominal; not adjusted for inflation)
    - Not Seasonally Adjusted
    - Weekly ending Monday
    Categories:
    - Date: Monday of each week (YYYY-MM-DD)
    - M2_Level: total M2 money supply in Billions of Dollars
    - M2_YoY_Growth: year-over-year percent change in M2
    Use Cases:
    - Monitoring money supply growth for inflation risk (rapid M2 expansion historically precedes inflation)
    - Federal Reserve balance sheet and quantitative easing / tightening analysis
    - Monetarist macroeconomic analysis
    FRED Series: WM2NS | Weekly Monday | Federal Reserve | Jan 1981 - present
    """
    keywords = "Date, M2_Level, M2_YoY_Growth, WM2NS, Federal Reserve, M2, M2 money supply, broad money, quantitative easing, monetary aggregates"
    Date          = dt(dtype=str,   unit=None)
    M2_Level      = dt(dtype=float, unit="Billions of Dollars")
    M2_YoY_Growth = dt(dtype=float, unit="%")


@dataclass
class FRED_M1(Table):
    name = "FRED M1 Money Supply"
    description = """
    Name: FRED M1 Money Supply (Monthly)
    Keywords:
    - Federal Reserve Economic Data
    - M1 Money Supply (narrow money aggregate)
    - Federal Reserve
    - M1 Components: physical currency in circulation plus demand deposits plus other checkable deposits plus travelers checks
    - Billions of Dollars (nominal; not adjusted for inflation)
    - Seasonally Adjusted
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - M1_Level: total M1 money supply in Billions of Dollars
    - M1_YoY_Growth: year-over-year percent change in M1
    Use Cases:
    - Measuring the most liquid transaction money in the economy
    - Tracking Federal Reserve reserve injection and withdrawal effects
    - Short-term liquidity and spending analysis
    FRED Series: M1SL | Monthly | Federal Reserve | Jan 1959 - present
    """
    keywords = "Date, M1_Level, M1_YoY_Growth, M1SL, Federal Reserve, M1, M1 money supply, narrow money, currency, demand deposits, liquidity"
    Date          = dt(dtype=str,   unit=None)
    M1_Level      = dt(dtype=float, unit="Billions of Dollars")
    M1_YoY_Growth = dt(dtype=float, unit="%")


# ── TRADE / EXTERNAL SECTOR ───────────────────────────────────────────────────

@dataclass
class FRED_TRADE_BALANCE(Table):
    name = "FRED Trade Balance"
    description = """
    Name: FRED Trade Balance - Goods and Services (Balance of Payments Basis)
    Keywords:
    - Federal Reserve Economic Data
    - Trade Balance (total exports minus total imports of goods and services)
    - Bureau of Economic Analysis
    - Balance of Payments Basis (transactions recorded when economic ownership changes; consistent with national accounts)
    - Millions of Dollars
    - Seasonally Adjusted
    - Trade Deficit when value is negative (imports exceed exports)
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Trade_Balance: net exports of goods and services in Millions of Dollars (negative value = trade deficit)
    Use Cases:
    - Net exports component of GDP calculation
    - U.S. competitiveness and current account analysis
    - Trade policy impact assessment
    FRED Series: BOPGSTB | Monthly | BEA | Jan 1992 - present
    """
    keywords = "Date, Trade_Balance, BOPGSTB, BEA, Bureau of Economic Analysis, trade balance, exports, imports, trade deficit, balance of payments, current account"
    Date          = dt(dtype=str,   unit=None)
    Trade_Balance = dt(dtype=float, unit="Millions of Dollars")


@dataclass
class FRED_USD_INDEX(Table):
    name = "FRED Nominal Broad USD Index"
    description = """
    Name: FRED Nominal Broad U.S. Dollar Index
    Keywords:
    - Federal Reserve Economic Data
    - Nominal Broad U.S. Dollar Index
    - Federal Reserve
    - Trade-Weighted Dollar (each partner currency is weighted by the share of bilateral U.S. trade with that country)
    - Index Jan 2006=100 (the USD value expressed relative to the January 2006 trade-weighted average, set to 100; above 100 means stronger than Jan 2006)
    - Not Seasonally Adjusted
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - USD_Index: trade-weighted nominal dollar index in Index Jan 2006=100
    Use Cases:
    - Import price and inflation pass-through analysis (stronger dollar lowers import prices, reducing inflation)
    - U.S. corporate earnings impact analysis (stronger dollar reduces the dollar value of overseas profits)
    - Emerging market stress analysis (stronger dollar causes capital outflows from emerging markets)
    FRED Series: DTWEXBGS | Daily | Federal Reserve | Jan 2006 - present
    """
    keywords = "Date, USD_Index, DTWEXBGS, Federal Reserve, nominal broad dollar index, trade-weighted, USD strength, currency"
    Date      = dt(dtype=str,   unit=None)
    USD_Index = dt(dtype=float, unit="Index Jan 2006=100")


# ── CONSUMER & BUSINESS SENTIMENT ────────────────────────────────────────────

@dataclass
class FRED_CONSUMER_SENTIMENT(Table):
    name = "FRED Consumer Sentiment"
    description = """
    Name: FRED University of Michigan Consumer Sentiment Index
    Keywords:
    - Federal Reserve Economic Data
    - University of Michigan Consumer Sentiment Index
    - Surveys of Consumers (monthly telephone survey conducted by the University of Michigan)
    - Forward-looking consumer confidence
    - Index 1966:Q1=100 (sentiment level expressed relative to the Q1 1966 survey baseline, set to 100)
    - Not Seasonally Adjusted
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Consumer_Sentiment: consumer confidence index in Index 1966:Q1=100 (higher = more optimistic about economy)
    Use Cases:
    - Predicting consumer spending; consumer spending accounts for approximately 70% of U.S. GDP
    - Leading indicator for economic turning points
    - Inflation expectations sub-component available within the same survey
    FRED Series: UMCSENT | Monthly | University of Michigan | Nov 1952 - present
    """
    keywords = "Date, Consumer_Sentiment, UMCSENT, University of Michigan, consumer sentiment index, consumer confidence, forward-looking, spending outlook"
    Date               = dt(dtype=str,   unit=None)
    Consumer_Sentiment = dt(dtype=float, unit="Index 1966:Q1=100")


@dataclass
class FRED_RETAIL_SALES(Table):
    name = "FRED Advance Retail Sales"
    description = """
    Name: FRED Advance Retail Sales - Retail Trade and Food Services
    Keywords:
    - Federal Reserve Economic Data
    - Advance Retail Sales (preliminary estimate released approximately 2 weeks after month-end)
    - U.S. Census Bureau
    - Retail Trade and Food Services
    - Nominal dollar value of sales (not adjusted for price changes)
    - Seasonally Adjusted
    - Millions of Dollars
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Retail_Sales: total retail and food services sales in Millions of Dollars
    - Retail_Sales_MoM: month-over-month percent change in retail sales
    - Retail_Sales_YoY: year-over-year percent change in retail sales
    Use Cases:
    - Real-time gauge of consumer goods demand; consumer spending is the largest component of GDP
    - Early read on personal consumption expenditures before the official PCE release
    - Sector-level spending analysis across auto, food, clothing, and electronics
    FRED Series: RSAFS | Monthly | U.S. Census Bureau | Jan 1992 - present
    """
    keywords = "Date, Retail_Sales, Retail_Sales_MoM, Retail_Sales_YoY, RSAFS, Census Bureau, advance retail sales, consumer spending, goods demand"
    Date             = dt(dtype=str,   unit=None)
    Retail_Sales     = dt(dtype=float, unit="Millions of Dollars")
    Retail_Sales_MoM = dt(dtype=float, unit="%")
    Retail_Sales_YoY = dt(dtype=float, unit="%")


# ── HOUSING ───────────────────────────────────────────────────────────────────

@dataclass
class FRED_HOUSING_STARTS(Table):
    name = "FRED Housing Starts"
    description = """
    Name: FRED New Privately-Owned Housing Units Started (Housing Starts)
    Keywords:
    - Federal Reserve Economic Data
    - Housing Starts
    - U.S. Census Bureau
    - New Privately-Owned Housing Units Started
    - Seasonally Adjusted Annual Rate (the monthly count scaled to reflect what the annual total would be at that pace)
    - Thousands of Units
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Housing_Starts: new residential construction starts in Thousands of Units (Seasonally Adjusted Annual Rate)
    Use Cases:
    - Leading indicator for construction sector activity and GDP
    - Lumber, building materials, and appliance demand forecasting
    - Housing cycle phase identification; highly sensitive to mortgage rate changes
    FRED Series: HOUST | Monthly | U.S. Census Bureau | Jan 1959 - present
    """
    keywords = "Date, Housing_Starts, HOUST, Census Bureau, housing starts, new construction, residential, homebuilding, SAAR, seasonally adjusted annual rate"
    Date           = dt(dtype=str,   unit=None)
    Housing_Starts = dt(dtype=float, unit="Thousands of Units (SAAR)")


@dataclass
class FRED_EXISTING_HOME_SALES(Table):
    name = "FRED Existing Home Sales"
    description = """
    Name: FRED Existing Home Sales
    Keywords:
    - Federal Reserve Economic Data
    - Existing Home Sales
    - National Association of Realtors
    - Resale of previously owned single-family homes, townhomes, condominiums, and co-ops
    - Seasonally Adjusted Annual Rate (the monthly count scaled to reflect what the annual total would be at that pace)
    - Number of Units
    - Monthly
    Categories:
    - Date: first day of month (YYYY-MM-DD)
    - Existing_Home_Sales: annualized count of previously owned homes sold in Number of Units (Seasonally Adjusted Annual Rate)
    Use Cases:
    - Housing market activity and affordability assessment
    - Measuring mortgage rate sensitivity; sales fall sharply when rates rise
    - Real estate sector and related services demand analysis
    FRED Series: EXHOSLUSM495S | Monthly | National Association of Realtors | Feb 2025 - present
    """
    keywords = "Date, Existing_Home_Sales, EXHOSLUSM495S, NAR, National Association of Realtors, existing home sales, housing market, affordability, SAAR"
    Date                = dt(dtype=str,   unit=None)
    Existing_Home_Sales = dt(dtype=float, unit="Number of Units (SAAR)")


# ── CREDIT & FINANCIAL CONDITIONS ────────────────────────────────────────────

@dataclass
class FRED_CREDIT_SPREADS(Table):
    name = "FRED Credit Spreads"
    description = """
    Name: FRED Credit Spreads - Investment Grade and High Yield
    Keywords:
    - Federal Reserve Economic Data
    - Moody's Seasoned Baa Corporate Bond Yield Spread (yield difference between Baa-rated bonds and the 10-year Treasury)
    - Baa (the lowest investment-grade credit rating assigned by Moody's Investors Service)
    - ICE BofA US High Yield Index Option-Adjusted Spread
    - Option-Adjusted Spread (the spread after removing the value of any embedded call or put options, isolating the pure credit risk premium)
    - High Yield Bonds (corporate bonds rated below investment grade; also called junk bonds)
    - Credit Spread (the extra yield investors demand above the risk-free Treasury rate to compensate for default risk)
    - Not Seasonally Adjusted
    - Daily
    Categories:
    - Date: date (YYYY-MM-DD)
    - BAA_Spread: Moody's Baa corporate yield minus 10-year Treasury yield in % (investment-grade credit risk premium)
    - HY_OAS: ICE BofA high yield option-adjusted spread in % (junk bond credit risk premium)
    Use Cases:
    - Financial stress and risk appetite monitoring; both spreads widen sharply in recessions
    - Credit tightening and easing cycle identification
    - Leading indicator for corporate defaults and economic downturns
    FRED Series: BAA10Y (from Jan 1986), BAMLH0A0HYM2 (from Dec 1996) | Daily
    """
    keywords = "Date, BAA_Spread, HY_OAS, BAA10Y, BAMLH0A0HYM2, Moody's, ICE BofA, credit spread, high yield, junk bonds, option-adjusted spread, financial conditions, default risk"
    Date       = dt(dtype=str,   unit=None)
    BAA_Spread = dt(dtype=float, unit="%")
    HY_OAS     = dt(dtype=float, unit="%")


@dataclass
class FRED_VIX(Table):
    name = "FRED VIX Volatility Index"
    description = """
    Name: FRED CBOE Volatility Index (VIX)
    Keywords:
    - Federal Reserve Economic Data
    - Chicago Board Options Exchange (CBOE) Volatility Index
    - VIX (measures the 30-day implied volatility of S&P 500 index options; a forward-looking fear gauge)
    - Implied Volatility (the market's forecast of likely price movement derived from option prices)
    - Index (dimensionless; roughly equals the market-implied annualized percent move of the S&P 500 over the next 30 days)
    - Not Seasonally Adjusted
    - Daily close
    Categories:
    - Date: date (YYYY-MM-DD)
    - VIX: CBOE VIX closing index level (10 to 20 = calm market, 20 to 30 = elevated stress, above 30 = high fear)
    Use Cases:
    - Market stress and risk-off environment detection
    - Options hedging cost and pricing context
    - Macro regime identification; low VIX indicates risk-on, high VIX indicates risk-off
    FRED Series: VIXCLS | Daily close | CBOE | Jan 1990 - present
    """
    keywords = "Date, VIX, VIXCLS, CBOE, Chicago Board Options Exchange, volatility index, fear gauge, implied volatility, S&P 500, market stress, risk-off"
    Date = dt(dtype=str,   unit=None)
    VIX  = dt(dtype=float, unit="Index")
