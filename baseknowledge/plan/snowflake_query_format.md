## Format for query from snowflake warehouse

## Description:
- the format provide you the way to access to data
- the format let you define:
    + selecting columns
    + perform operation among columns
    + join with condition

## Format
```
{
'select': {
            'column1_name': {
                        'origin':,
                        'operation':,
                    },
            'column2_name': {
                        'origin':,
                        'operation':,
                    },
        },
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
```

## RULES
- 'select': dict including columns of interested
  + key is column name
  + value is also a dictionary
  + if origin is specified then the key of select is alias
  + if there is origin, operation is None
  + if there is operation, origin is None
  + operation is where you are allowed to perform cross column operation

_Example_: the below json means you select gdp_growth column in the table and rename to gdp_growth_k, no operation because of origin
  ```
  {
  'select': {
      'gdp_growth_k': {
          'origin': gdp_growth,
          'operation': None
          }
      }
  } 
  ```
_Example_: the below json means you perform operation gdp column divided by population column, the result will be a new column name gdp_per_capita, no origin because there is operation
  ```
  {
  'select': {
      'gdp_per_capita': {
          'origin': None,
          'operation': 'gdp/population'
          }
      }
  } 
  ```
- 'join': dict of joining tables:
  + specify name of table to join with
  + type of join: left join, right join, join
  + list of joining condition:
    * type_condition: 'and' or 'or'
    * LHS: column on left hand side of the condition
    * condition_operator: <, >, = 
    * RHS: column on right hand side of the 
  + when you join table, make sure in the 'select', you have to specify the column of table: `table_name.column`, there might be similar name column across table
_Example_: 
```
{
'select': {
      ...column to select...
      
  } 
'from': gdp_table
'join': {
    'table_name': cpi_table
    'type_join': 'left join' 
    'on': {
        'type_condition': 
        
    }
  }
}
```
