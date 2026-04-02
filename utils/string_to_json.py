import json
import sys
import re

from sympy.codegen.ast import Raise
from sympy.simplify.hyperexpand import try_lerchphi

if __name__ == '__main__':
    query = sys.argv[1]
    if not re.search("^--query=",query):
        raise ("Invalid argument, must be --query=your_string_input")

    query = query.replace("--query=","")
    query = query.replace("'",'"')
    print(query)
    try:
        jsondata = json.loads(query)
    except json.decoder.JSONDecodeError:
        raise ("Cannot parses query to json")

    try:
        with open("jsondata.json", "w") as json_file:
            json.dump(jsondata, json_file)
            json_file.close()
    except IOError:
        print("json format cannot be written")



