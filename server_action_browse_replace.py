"""
SERVER ACTIONS REPLACEMENT

GENERIC SCRIPT TO CHANGE FUNCTION FROM x_function(17) to x_function(env['model'].browse(17))
"""


env.cr.execute(r"""
WITH affected_actions AS (
    SELECT id 
      FROM ir_act_server
     WHERE id IN (
        SELECT res_id
          FROM ir_model_data
         WHERE module='__cloc_exclude__'
           AND name ilike 'document_workflow_migrated_to_server_action_%'
           AND model='ir.actions.server'
    ) AND code ilike '%x_function(%'
)
UPDATE ir_act_server
SET code = REGEXP_REPLACE(
    code,
    'records\.x_function\(\s*(\d+)\s*\)',
    'x_function(env[''model''].browse(\1))',
    'g'
)
WHERE id IN (SELECT id FROM affected_actions) 
  AND code ~ 'records\.x_function\(\s*\d+\s*\)'
RETURNING CONCAT('- #', id, ':',name->>'en_US', ' -> Updated');
""")

result = [
    "UPDATED RECORDS:"
] + [data[0] for data in env.cr.fetchall()]
env.cr.commit()
log('\n'.join(result))
