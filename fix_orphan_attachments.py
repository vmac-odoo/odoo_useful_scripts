"""
Orphan Attachments Fixer

[USE IT BY YOUR OWN RISK!]

This scripts helps when you have orphan attachments, that means that by some reason (by the moment idk) 
the record linked to some attachment has been deleted but the attachment still alive and believes that 
the record continue in the database.

Ex. Attachment X has res.partner model and res_id 555, but if I search it, it has been deleted

This raise a issue in frontend related to getUrl searching func includes... and maybe in other cases could appear this.

Params:
- generate_sql_and_csv: if true, will generate a full csv report with the modified records and some information, 
and the most important: A SQL file, very helpful because in SAAS databases you cannot use this script, but you can 
download the database locally, run this script, get the sql file and execute the queries in a scheduled action.
- print_data: if true, will show very simple report at the console.
- strategy: To fix this, there are two ways to fix it
    1. update: that means that will set null the res_model, res_id and res_field. The attachment will be a fully orphan
    2. delete: that means that you dont need this attachments and they can go to the trash! [NO ROLLBACK]

[USE IT BY YOUR OWN RISK!]

Created for opw-4703030 and opw-4729580
Created by: vmac-odoo
"""

import csv
from itertools import groupby
from psycopg2 import sql


class FixOrphanAttachments:
    
    def __init__(self, generate_sql_and_csv=False, print_data=True, strategy='update',):
        self.dir = '/Users/nefonfo/Desktop/report_fix'
        self.generate_sql_and_csv=generate_sql_and_csv
        self.sql = []
        self.print_data=print_data
        self.strategy=strategy
     
    def search_attachments(self):
        env.cr.execute(
            """
            SELECT
                res_model,
                res_id
            FROM ir_attachment
            WHERE
                type = 'binary'
                AND res_id > 0
                AND res_model IS NOT NULL
            GROUP BY
                res_model,
                res_id
            """
        )
        results = env.cr.fetchall()
        results.sort(key=lambda x: x[0])
        return results
    
    def get_attachments_with_phantom_records(self, ordered_attachments):
        records_to_delete = {}
        for res_model, attachments in groupby(ordered_attachments, key=lambda k: k[0]):
            table = res_model.replace('.', '_')
            related_attachments = [attachment[1] for attachment in list(attachments)]
            env.cr.execute(sql.SQL(
                """
                SELECT id
                    FROM {}
                WHERE id IN %s               
                """
            ).format(
                sql.Identifier(table)
            ), [tuple(related_attachments)])
            
            results = env.cr.fetchall()
            found_records = set([r_id for r_id, in results])
            
            missing_attachments = set(related_attachments) - found_records
            if missing_attachments:
                records_to_delete[table] = tuple(missing_attachments)
        return records_to_delete
    
    def execute_wrapper(self, query, vals):
        def format_sql_value(val):
            if isinstance(val, tuple):
                return f"({', '.join(repr(v) for v in val)})"
            return repr(val)

        if self.generate_sql_and_csv:
            safe_query = query.replace('%s', '{}')
            formatted_vals = [format_sql_value(v) for v in vals]
            self.sql.append(safe_query.format(*formatted_vals))
        
        env.cr.execute(query, vals)
        return env.cr.fetchall()
    
    def fix_with_strategy(self, table_ids_to_delete):
        csv_report = []
        for model, ids in table_ids_to_delete.items():
            if not ids:
                continue
            if self.strategy == 'delete':
                results = self.execute_wrapper(
"""DELETE FROM ir_attachment
WHERE res_model = %s AND res_id IN %s
RETURNING id, name, res_model, res_id;""",
                    [model.replace('_', '.'), ids]
                )
            elif self.strategy == 'update':
                results = self.execute_wrapper(
"""WITH old_rows AS (
  SELECT id, name, res_model, res_id, res_field
  FROM ir_attachment
  WHERE res_model = %s AND res_id IN %s
),
updated AS (
  UPDATE ir_attachment
  SET res_model = NULL, res_id = NULL, res_field = NULL
  WHERE id IN (SELECT id FROM old_rows)
  RETURNING id
)
SELECT o.id, o.name, o.res_model, o.res_id, o.res_field
FROM old_rows o
JOIN updated u ON o.id = u.id;""",
                    [model.replace('_', '.'), ids]
                )
            csv_report.extend(results)
        return csv_report

    def pre_report(self, report):
        print('#############################')
        print('#######    REPORT    ########')
        print('#############################')
        
        print(f"***** STRATEGY - {self.strategy} *****")

        print(f'TABLE AND COUNTS OF ROWS THAT WILL BE {self.strategy}')
        res_str = '\n'.join([f"- TABLE {table}: {len(count)} items!" for table, count in report.items()])
        print(res_str)
    
    def create_sql_file(self):
        if not len(self.sql):
            print('NO SQL GENERATED')
            return
        file_dir = f"{self.dir}/sql_file.sql"
        with open(file_dir, "w", encoding="utf-8") as f:
            f.write('\n\n'.join(self.sql))
        print(f'SQL FILE GENERATED AT: {file_dir}')
        
    def create_csv_file(self, report):
        if not len(report):
            print('NO REPORT CSV GENERATED')
            return
        file_dir = f"{self.dir}/report_attachments.csv"
        header = ['id', 'name', 'res_model', 'res_id']
        if self.strategy == 'update':
            header.append('res_field')
        report.insert(0, tuple(header))
        with open(file_dir, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(report)
        print(f'CSV FILE GENERATED AT: {file_dir}')

        
    def run(self):
        attachments = self.search_attachments()
        table_ids_to_delete = self.get_attachments_with_phantom_records(attachments)
        if self.print_data:
            self.pre_report(table_ids_to_delete)
        csv_report = self.fix_with_strategy(table_ids_to_delete)
        if self.generate_sql_and_csv:
            self.create_sql_file()
            self.create_csv_file(csv_report)
        env.cr.commit()
    
fix = FixOrphanAttachments(True)
fix.run()