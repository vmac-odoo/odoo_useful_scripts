"""
Script that generates Python code for Odoo Scheduled Action
to fix account_analytic_line migration.

This script fixes the issue when you change the system parameter analytic.project_plan

YOU MUST NEED A BACKUP.

x_plan2_id must be replaced to the old field that had the content of the ids.
account_id is the target.

OPW-5359529
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection configuration
BACKUP_DB = {
    'dbname': 'db-backup',
    'user': 'odoo'
}

TEST_DB = {
    'dbname': 'db-with-issue',
    'user': 'odoo'
}

def get_migration_data():
    """
    Gets the necessary data from both databases to generate the fix script
    """
    # Connect to db-backup
    conn_backup = psycopg2.connect(**BACKUP_DB)
    cur_backup = conn_backup.cursor(cursor_factory=RealDictCursor)
    
    # Connect to db-with-issue
    conn_test = psycopg2.connect(**TEST_DB)
    cur_test = conn_test.cursor(cursor_factory=RealDictCursor)
    
    # Get IDs of records with NULL account_id in test
    cur_test.execute("""
        SELECT id 
        FROM account_analytic_line 
        WHERE account_id IS NULL
        ORDER BY id
    """)
    error_ids = [row['id'] for row in cur_test.fetchall()]
    
    print(f"Total records with error: {len(error_ids)}")
    
    # Get correct x_plan2_id values from backup
    # Only for IDs that have errors
    if error_ids:
        cur_backup.execute("""
            SELECT id, x_plan2_id
            FROM account_analytic_line
            WHERE id = ANY(%s)
            AND x_plan2_id IS NOT NULL
            ORDER BY id
        """, (error_ids,))
        
        correct_data = cur_backup.fetchall()
    else:
        correct_data = []
    
    cur_backup.close()
    conn_backup.close()
    cur_test.close()
    conn_test.close()
    
    return correct_data

def generate_odoo_scheduled_action_code(data):
    """
    Generates Python code for an Odoo Scheduled Action
    """
    lines = []
    lines.append("# Copy this code into an Odoo Scheduled Action")
    lines.append("")
    lines.append("# Changes dictionary: {id: correct_account_id}")
    lines.append("CHANGES = {")
    
    # Add data to dictionary
    for i, row in enumerate(data):
        comma = "," if i < len(data) - 1 else ""
        lines.append(f"    {row['id']}: {row['x_plan2_id']}{comma}")
    
    lines.append("}")
    lines.append("")
    lines.append("def apply_changes():")
    lines.append("    try:")
    lines.append("        _logger.info(f'Applying {len(CHANGES)} changes...')")
    lines.append("        ")
    lines.append("        # Create temporary table")
    lines.append("        env.cr.execute('''")
    lines.append("            CREATE TEMP TABLE IF NOT EXISTS temp_account_fixes (")
    lines.append("                id INTEGER PRIMARY KEY,")
    lines.append("                account_id INTEGER")
    lines.append("            )")
    lines.append("        ''')")
    lines.append("        ")
    lines.append("        # Insert changes in batches")
    lines.append("        batch_size = 1000")
    lines.append("        items = list(CHANGES.items())")
    lines.append("        ")
    lines.append("        for i in range(0, len(items), batch_size):")
    lines.append("            batch = items[i:i + batch_size]")
    lines.append("            values = ','.join([f'({record_id},{account_id})' for record_id, account_id in batch])")
    lines.append("            ")
    lines.append("            env.cr.execute(f'''")
    lines.append("                INSERT INTO temp_account_fixes (id, account_id)")
    lines.append("                VALUES {values}")
    lines.append("            ''')")
    lines.append("        ")
    lines.append("        # Single UPDATE using JOIN with temp table")
    lines.append("        env.cr.execute('''")
    lines.append("            UPDATE account_analytic_line AS aal")
    lines.append("            SET account_id = taf.account_id")
    lines.append("            FROM temp_account_fixes AS taf")
    lines.append("            WHERE aal.id = taf.id")
    lines.append("        ''')")
    lines.append("        ")
    lines.append("        affected = env.cr.rowcount")
    lines.append("        env.cr.commit()")
    lines.append("        ")
    lines.append("        # Clean up temp table")
    lines.append("        env.cr.execute('DROP TABLE IF EXISTS temp_account_fixes')")
    lines.append("        ")
    lines.append("        _logger.info(f'✓ Updated {affected} records')")
    lines.append("        ")
    lines.append("    except Exception as e:")
    lines.append("        env.cr.rollback()")
    lines.append("        raise UserError(str(e))")
    lines.append("")
    lines.append("apply_changes()")
    
    return "\n".join(lines)

def main():
    print("Connecting to databases...")
    data = get_migration_data()
    
    print(f"\nGenerating code for Odoo Scheduled Action...")
    odoo_code = generate_odoo_scheduled_action_code(data)
    
    # Save code for Odoo
    odoo_file = 'odoo_scheduled_action_code.py'
    with open(odoo_file, 'w', encoding='utf-8') as f:
        f.write(odoo_code)
    
    print(f"✓ Code for Odoo generated: {odoo_file}")
    print(f"\n{'='*60}")
    print(f"Total changes: {len(data)}")
    print(f"{'='*60}")
    print(f"\nSteps to apply in Odoo:")
    print(f"  1. Go to Settings > Technical > Automation > Scheduled Actions")
    print(f"  2. Create a new planified / server action")
    print(f"  3. Copy and paste the content of: {odoo_file}")
    print(f"  4. Save and execute manually")

if __name__ == "__main__":
    main()
