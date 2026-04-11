import json
import os
import ast

__REQUIRE_FIELD__ = {
'select': [
            {
            'column_name':'',
            'origin': '',
            'operation': ''
            }
        ],
'from': '',
'join': [
    {
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
],
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

#ERROR REPORT
def InvalidKeyError(valid_field, input_field):
    return f"INVALID KEY: expected {valid_field}, instead found {input_field}"

def InvalidFormatError(host, valid_format):
    return f"INVALID FORMAT: {host} must be {valid_format}"

def MissingValueError(host, value_missing, addition = ""):
    return f"MISSING VALUE: {host} must have {value_missing} {addition}"

def ParsingError(host, required_fields):
    return f"PARSING ERROR: {host} must be {required_fields}"

def _json_file_loader(json_file):
    if not json_file.endswith(".json"):
        raise "file must be in .json"
    if not os.path.exists(json_file):
        raise 'file does not exist'
    with open(json_file) as f:
        return json.load(f)

#Utilities
def condition_parse(condition_type,condition_field):
    return f"{condition_type} {condition_field['LHS']} {condition_field['condition_operator']} {condition_field['RHS']}\n"

#Parse Function
def json_parser(json_file: str|dict):
    """
    Parse Formatted string to SNOWFLAKE SQL Query
    :param json_file | dict | parsable string to json:
    :return SQL query:
    """
    data = json_file
    if not isinstance(json_file, dict):
        try:
            try:
                data = _json_file_loader(json_file)
            except:
                pass
            try:
                data = json.dumps(json_file)
            except:
                pass

            data = ast.literal_eval(json_file)
        except:
            return InvalidFormatError("input", "either dict, path to json file or parsable string to json")



    if ("select" not in data and "from" not in data
        and data['select'] is None and data['from'] is None
        and len(data["select"]) == 0 and len(data["from"]) == 0):

        return "'select' and 'from' are strictly required for SQL query"

    #Check select
    SQLquery = []
    SQLquery.append("SELECT\n")
    if data['select'] is not None and not isinstance(data["select"], list):
        return "'select' must be a list"
    for ci, column in enumerate(data["select"]):
        column_query = ""
        if column.keys() != __REQUIRE_FIELD__["select"][0].keys():
            return InvalidKeyError(__REQUIRE_FIELD__["select"][0].keys(), column.keys())

        if column['origin'] is not None and len(column['origin']) > 0:
            column_query += column['origin']
        elif column['operation'] is not None and len(column['operation']) > 0:
            column_query += f"({column['operation']})"
        elif column['column_name'] is not None:
            column_query += column['column_name'] + '\n'
            SQLquery.append(column_query)
            continue

        if column['column_name'] is None or len(column['column_name']) == 0:
            return MissingValueError('column_name', 'value', 'if operation or origin is not None')


        column_query += f" AS {column['column_name']}" + '\n'
        SQLquery.append(column_query)

    SQLquery.append(f"FROM {data['from']}\n")

    if 'join' in data and data['join'] is not None and len(data['join']) > 0:
        if not isinstance(data['join'], list):
            return InvalidFormatError('join', 'list')
        for ti, join_table in enumerate(data['join']):
            join_query = ""
            if join_table.keys() != __REQUIRE_FIELD__["join"][0].keys():
                return InvalidKeyError(__REQUIRE_FIELD__["join"][0].keys(), join_table.keys())
            try:
                if join_table['type_join'] is None or len(join_table['type_join']) == 0:
                    return MissingValueError('type_join', 'value')
            except Exception as e:
                return ParsingError(join_table['type_join'], 'string') + f'\n{e}'
            try:
                if join_table['table_name'] is None or len(join_table['table_name']) == 0:
                    return MissingValueError('table_name', 'value')
            except Exception as e:
                return ParsingError(join_table['table_name'], 'string') + f'\n{e}'

            join_query += join_table['type_join'].upper() + " " +join_table['table_name'] + '\n'
            SQLquery.append(join_query)


            if "on" in join_table and join_table['on'] is not None:
                if not isinstance(join_table['on'], list):
                    return InvalidFormatError('on', 'list')
                for ji, join_condition in enumerate(join_table['on']):
                    if join_condition.keys() != __REQUIRE_FIELD__['join'][0]["on"][0].keys():
                        return InvalidKeyError(",".join(__REQUIRE_FIELD__['join'][0]["on"][0].keys()), ",".join(join_condition.keys()))


                    if ji == 0:
                        SQLquery.append(condition_parse('ON', join_condition))
                    else:
                        SQLquery.append(condition_parse(join_condition['type_condition'].upper(), join_condition))

    if "where" in data and data['where'] is not None and len(data['where']) > 0:
        if not isinstance(data['where'], list):
            return InvalidFormatError('where', 'list')

        for wi, where_cond in enumerate(data['where']):
            if where_cond.keys() != __REQUIRE_FIELD__['where'][0].keys():
                return InvalidKeyError(__REQUIRE_FIELD__['where'][0].keys(), where_cond.keys())


            if wi == 0:
                SQLquery.append(condition_parse('WHERE', where_cond))
            else:
                SQLquery.append(condition_parse(where_cond['type_condition'].upper(), where_cond))

    if 'group_by' in data and data['group_by'] is not None and len(data['group_by']) > 0:
        if not isinstance(data['group_by'], list):
            return InvalidFormatError('group_by', 'list')

        SQLquery.append(f"GROUP BY {",".join(data['group_by'])}\n")

    if 'having' in data and data['having'] is not None and len(data['having']) > 0:
        if not isinstance(data['having'], list):
            return InvalidFormatError('having', 'list')

        for ih, having_cond in enumerate(data['having']):
            if having_cond.keys() != __REQUIRE_FIELD__['having'][0].keys():
                return InvalidKeyError(__REQUIRE_FIELD__['having'][0].keys(), having_cond.keys())


            if ih == 0:
                SQLquery.append(condition_parse('HAVING', having_cond))
            else:
                SQLquery.append(condition_parse(having_cond['type_condition'].upper(), having_cond))

    return ''.join(SQLquery)

if __name__ == '__main__':
    input_prompt = """{
        'select': [
                    {
                    'column_name':'country_name',
                    'origin': '',
                    'operation': ''
                    },
                    {
                        'column_name': 'region_name',
                        'origin': 'region',
                        'operation': ''
                    },
                    {
                        'column_name': 'country_name',
                        'origin': '',
                        'operation': 'gdp/capita'
                    }
                ],
        'from': 'country_table',
        'join': [
            {
                'table_name':'country_table_2',
                'type_join':'join',
                'on': [
                        {
                            'type_condition':'on',
                            'LHS':'name',
                            'condition_operator':'=',
                            'RHS':'name',
                        }
                    ]
            },
        ],
        'where':[
                        {
                            'type_condition':'and',
                            'LHS':'name',
                            'condition_operator':'is not',
                            'RHS':'null',
                        }
        ],
        'group_by': ['country_name'],
        'having': [
                        {
                            'type_condition':'and',
                            'LHS':'COUNT(country_name)',
                            'condition_operator':'>',
                            'RHS':'0',
                        }
        ],
    }"""
    print(json_parser(input_prompt))



