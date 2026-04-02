from bs4 import BeautifulSoup
import requests
from pathlib import Path
from url import Url
from urllib.parse import urljoin
import sys
import re
import logging
#logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s', filename='intermediate_response.json')

ROOT_DIR = Path(__file__).resolve().parent

"""Wolrdometer Website for GDP"""

def request_from_Worldometer(target:str):
    with open(ROOT_DIR / "intermediate_response.txt", "w", encoding="utf-8") as file:
        url = urljoin(Url.Worldometer_GDP, target)
        if not Url.valid_url(url):
            file.write(f"""Invalid URL: {url}""")
            file.close()
            return False

        request = requests.get(url)
        html_parser = BeautifulSoup(request.content, "html.parser")
        tables = html_parser.find_all("table")
        output = {"table": []}
        if len(tables) == 0:
            file.write("Schema change")
        for table in tables:
            table_content = {"header": [], "body": []}
            for tr in table.find_all("tr"):
                if all(tag.name == "th" for tag in tr.find_all(recursive=False)):
                    for th in tr.find_all("th"):
                        table_content["header"].append(th.find("span").get_text())
                else:
                    data = []
                    for td in tr.find_all("td"):
                        data.append(td.get_text())
                    table_content["body"].append(data)
            output["table"].append(table_content)

        for idx, table in enumerate(output["table"]):
            file.write(f"""
            <Table{idx}>\n
                <Headers>{table["header"]}</Headers>\n
                <Body>{table["body"]}</Body>\n
            </Table{idx}>
            """)
        file.close()
if __name__ == "__main__":
    if len(sys.argv) > 1:
        target:str
        if re.findall("^--target=", sys.argv[-1]):
            target = sys.argv[-1].replace("--target=", "")
        else:
            target = "Invalid"
        tables = request_from_Worldometer(target)

