import json
import os

__JSON_FORMAT__ = """
{
'select': [
            'column1_name': {
                        'origin':,
                        'operation':,
                    },
            'column2_name': {
                        'origin':,
                        'operation':,
                    },
        ],
'from': table_name,
'join': {
        'table_name':,
        'type_join': 
        'on': [
                {
                    'type_condition':,
                    'LHS':,
                    'condition_operator:,
                    'RHS:,
                },
                {
                    'type_condition':,
                    'LHS':,
                    'condition_operator:,
                    'RHS:,
                }
            ]         
    }
'where':[
                {
                    'type_condition':,
                    'LHS':,
                    'condition_operator:,
                    'RHS:,
                },
                {
                    'type_condition':,
                    'LHS':,
                    'condition_operator:,
                    'RHS:,
                },
            ]
'group_by': [column1, column2, ...]
'having': [
                {
                    'type_condition':,
                    'LHS':,
                    'condition_operator:,
                    'RHS:,
                },
                {
                    'type_condition':,
                    'LHS':,
                    'condition_operator:,
                    'RHS:,
                },
            ]
}
"""


__REQUIRE_FIELD__ = {
'select': [
            {
            'column_name':'',
            'origin': '',
            'operation': ''
            }
        ],
'from': '',
'join': {
        'table_name':'',
        'type_join':'',
        'on': [
                {
                    'type_condition':'',
                    'LHS':'',
                    'condition_operator':'',
                    'RHS':'',
                }
            ]
    },
'where':[
                {
                    'type_condition':'',
                    'LHS':'',
                    'condition_operator':'',
                    'RHS':'',
                }
],
'group_by': [],
'having': [
                {
                    'type_condition':'',
                    'LHS':'',
                    'condition_operator':'',
                    'RHS':'',
                }
],
}


def _json_file_loader(json_file):
    if not json_file.endswith(".json"):
        raise "file must be in .json"
    if not os.path.exists(json_file):
        raise 'file does not exist'
    with open(json_file) as f:
        return json.load(f)

def json_parser(json_file):
    data = _json_file_loader(json_file)
    sql_query = ""
    for key in __REQUIRE_FIELD__:
        if key not in data:
            assert False, f"{key} is not in {__REQUIRE_FIELD__}"
        if isinstance(__REQUIRE_FIELD__[key], list):




