"""
COMPARE MISSING CONSTRAINTS

Script helpful to identify which constraints are missing, it compares a clean database vs a old one.

Important: Both dbs should have the same apps installed.

Created for opw-4712058
Created by: vmac-odoo
"""

import psycopg2
import csv


class Database:
    def __init__(self, dbname):
        self.conn = psycopg2.connect(
            dbname=dbname,
            user='<user>',
            host="<host>",
            port="5432"
        )
        self.cr = self.conn.cursor()
        
    def kill(self):
        self.cr.close()
        self.conn.close()
    
    def get_all_tables(self):
        self.cr.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE';
        """)
        return set(table for table, in self.cr.fetchall())
    
    def get_table_constraints(self, table):
        self.cr.execute("""
            SELECT conname
            FROM pg_constraint
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            WHERE pg_class.relname = %s;
        """, [table])
        return set(constraint for constraint, in self.cr.fetchall())
        
class Report:
    
    general_report_sheet = '/<dir>/general_report_sheet.csv'
    full_report_sheet = '/<dir>/full_report_sheet.csv'
    
    def __init__(self, data):
        self.results = data
        self.generate_general_info()
        self.generate_full_report()
        
    def generate_general_info(self):
        columns = ['table', 'missing constraints (count)']
        general_data = [
            {
                'table': table,
                'missing constraints (count)': len(constraints)
            }
            for table, constraints in self.results.items()
        ]
        with open(self.general_report_sheet, 'w',  newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            writer.writerows(general_data)
            print(f'REPORT SAVED AT: {self.general_report_sheet}')
        self.display_general_info(general_data)
    
    def display_general_info(self, general_data):
        print('##########################################')
        print('##########   GENERAL REPORT    ###########')
        print('##########################################')
        report_str = [f"- TABLE: {gen_data['table']} - HAS {gen_data['missing constraints (count)']} MISSING CONSTRAINTS!" for gen_data in general_data]
        print('\n'.join(report_str))
    
    def generate_full_report(self):
        columns = ['constraint', 'table']
        full_report = [
            {
                'constraint': constraint,
                'table': table
            }
            for table, constraints in self.results.items()
            for constraint in constraints
        ]
        with open(self.full_report_sheet, 'w',  newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            writer.writerows(full_report)
            print(f'REPORT SAVED AT: {self.full_report_sheet}')
        
clean = Database('<clean-db-name>')
old = Database('<old-db-name>')

c_tables = clean.get_all_tables()
o_tables = old.get_all_tables()

tables_to_check = o_tables & c_tables
results = {}

for table in tables_to_check:
    missing_constraints = clean.get_table_constraints(table) - old.get_table_constraints(table)
    if missing_constraints:
        results[table] = missing_constraints
    
Report(results)
    
clean.kill()
old.kill()