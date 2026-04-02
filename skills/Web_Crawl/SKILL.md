
---
Name: request Worldometer GDP data
description: Get a list of table to match to provided GDP schema
---
## When to use
Use this to request GDP of specific country from Worldometer when needed
## Skill location
skills/Web_Crawl/request_Worldometer_method.py
## Output Location
skills/Web_Crawl/intermediate_response.txt
## Valid Input Restricted
Some country name will be converted to abbreviation-initialism style so make sure you try any possible choices before determine the skill does bot work
for country with single word
/gdp/[country in lower case]-gdp/
for country with multiple word
/gdp/[country_with_multuple_word in lower case]-gdp/

## Skill Does Not Work Situation
if after running the skill, output is False, then tell data is currently unavailable or the input format is wrong, Some countries need full name not Abbreviation
if after running the skill, output location is empty or schema change, then you can try to fetch data directly using this url https://www.worldometers.info + [target]

## How to Use
DONT read output file before calling the skill
Before calling, need to know EXACTLY the country to search for, else ask
Call the script vie the agent's tool interface
the target is name of country 
agent must match target with values in Valid Input Restricted
if there is no matched target, the target country is not in the known agent knowledge
---bash
metadata/request_Worldometer_method.py --target=[target]
clean the output location afterward


