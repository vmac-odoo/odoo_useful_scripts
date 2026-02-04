"""
SCRIPT TO FIX ISSUE AFTER UPGRADE, SOME analytic_distribution BY SOME REASON HAS FOR EXAMPLE {"285,285": 100.0}, that generates 200%

To fix this issue we need to change the value but sql is not enough because some values need to be recomputed, because if you go to profit/loss the values could dismatch

OPW-5890817
"""

from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

msgs = []

def _log_msgs(msg, header=False):
    msg = msg if not header else f"\n{header*10}\n{msg}\n{header*10}\n"
    _logger.info(msg)
    msgs.append(msg)

def _progress_bar(current, total, bar_length=50):
    """Generate a progress bar string"""
    progress = float(current) / float(total)
    arrow = '█' * int(round(progress * bar_length))
    spaces = '░' * (bar_length - len(arrow))
    percent = round(progress * 100, 2)
    return f'[{arrow}{spaces}] {percent}% ({current}/{total})'

# Backup
env.cr.execute("""
CREATE TABLE IF NOT EXISTS account_move_line_analytic_backup AS 
SELECT id, analytic_distribution, move_id, write_date
FROM account_move_line 
WHERE analytic_distribution IS NOT NULL;
""")
_log_msgs("BACKUP CREATED!", "=")
env.cr.commit()

# Get all lines to update grouped by move_id
env.cr.execute("""
SELECT 
    id,
    (
        SELECT jsonb_object_agg(
            array_to_string(
                ARRAY(
                    SELECT DISTINCT unnest(string_to_array(key, ','))::int 
                    ORDER BY 1
                ), 
                ','
            ),
            value
        )
        FROM jsonb_each(analytic_distribution)
    ) as new_values,
    move_id
FROM account_move_line
WHERE analytic_distribution IS NOT NULL 
  AND parent_state = 'posted'
  AND EXISTS (
      SELECT 1 
      FROM jsonb_each_text(analytic_distribution) 
      WHERE array_length(string_to_array(key, ','), 1) != 
            (SELECT count(DISTINCT x) FROM unnest(string_to_array(key, ',')) x)
  )
ORDER BY move_id;
""")

results = env.cr.fetchall()
_log_msgs(f"FOUND {len(results)} LINES TO UPDATE!", "=")

# Group by move_id
lines_by_move = defaultdict(list)
for aml_id, new_dist, move_id in results:
    lines_by_move[move_id].append((aml_id, new_dist))

total_moves = len(lines_by_move)
_log_msgs(f"GROUPED INTO {total_moves} MOVES", "=")

# Track results
fixed_moves = []  # (move, lines_fixed, lines_total)
unfixed_moves = []  # (move, lines_failed, lines_total, errors)
total_lines_fixed = 0
total_lines_failed = 0
processed_count = 0

# Process by move
for move_id, lines in lines_by_move.items():
    processed_count += 1
    move = env['account.move'].browse(move_id)
    
    # Progress bar
    progress = _progress_bar(processed_count, total_moves)
    _log_msgs(f"\n{progress}")
    _log_msgs(f"PROCESSING MOVE: {move.name} (#{move_id}) - {len(lines)} lines", "-")
    
    lines_fixed_in_move = 0
    lines_failed_in_move = 0
    move_errors = []
    
    # Update all lines in the move
    for aml_id, new_dist in lines:
        try:
            env['account.move.line'].browse(aml_id).write({
                'analytic_distribution': new_dist
            })
            lines_fixed_in_move += 1
            total_lines_fixed += 1
            _log_msgs(f"  ✓ Updated line #{aml_id}")
        except Exception as e:
            error_msg = str(e)
            lines_failed_in_move += 1
            total_lines_failed += 1
            move_errors.append(f"Line #{aml_id}: {error_msg}")
            _log_msgs(f"  ✗ ERROR updating line #{aml_id}: {error_msg}", "!")
    
    # Categorize move
    if lines_failed_in_move == 0:
        # All lines fixed
        fixed_moves.append((move, lines_fixed_in_move, len(lines)))
        _log_msgs(f"  ✓ MOVE FULLY FIXED: {lines_fixed_in_move}/{len(lines)} lines")
    else:
        # Some or all lines failed
        unfixed_moves.append((move, lines_failed_in_move, len(lines), move_errors))
        _log_msgs(f"  ⚠ MOVE PARTIALLY/NOT FIXED: {lines_fixed_in_move}/{len(lines)} lines fixed, {lines_failed_in_move} failed")
    
    # Commit every N moves to avoid very long transactions
    if processed_count % 10 == 0:
        env.cr.commit()
        _log_msgs(f"BATCH COMMITTED ({processed_count}/{total_moves} moves processed)", "$")

# Final commit
env.cr.commit()

# Final summary
_log_msgs(f"\n{_progress_bar(total_moves, total_moves)}", "=")
_log_msgs(f"\nPROCESSING COMPLETE!", "=")
_log_msgs(f"TOTAL LINES FIXED: {total_lines_fixed}", "=")
_log_msgs(f"TOTAL LINES FAILED: {total_lines_failed}", "=")
_log_msgs(f"TOTAL MOVES PROCESSED: {total_moves}", "=")

# Fixed moves summary
_log_msgs(f"\n✓ FIXED MOVES ({len(fixed_moves)}):", "@")
if fixed_moves:
    fixed_summary = '\n'.join([
        f'  - {m.name} (#{m.id}) - {lines_fixed}/{lines_total} lines' 
        for m, lines_fixed, lines_total in fixed_moves
    ])
    _log_msgs(fixed_summary)
else:
    _log_msgs("  (none)")

# Unfixed moves summary
_log_msgs(f"\n⚠ UNFIXED/PARTIALLY FIXED MOVES ({len(unfixed_moves)}):", "@")
if unfixed_moves:
    unfixed_summary = '\n'.join([
        f'  - {m.name} (#{m.id}) - {lines_failed}/{lines_total} lines failed\n    Errors: {"; ".join(errors[:3])}{"..." if len(errors) > 3 else ""}' 
        for m, lines_failed, lines_total, errors in unfixed_moves
    ])
    _log_msgs(unfixed_summary)
else:
    _log_msgs("  (none)")

# Statistics
success_rate = round((total_lines_fixed / (total_lines_fixed + total_lines_failed) * 100), 2) if (total_lines_fixed + total_lines_failed) > 0 else 0
move_success_rate = round((len(fixed_moves) / total_moves * 100), 2) if total_moves > 0 else 0

_log_msgs(f"\nSTATISTICS:", "=")
_log_msgs(f"Line Success Rate: {success_rate}%")
_log_msgs(f"Move Success Rate: {move_success_rate}%")
_log_msgs(f"Fully Fixed Moves: {len(fixed_moves)}/{total_moves}")
_log_msgs(f"Unfixed/Partial Moves: {len(unfixed_moves)}/{total_moves}")

# Final log
env['ir.logging'].create({
    'name': 'fix_200',
    'type': 'server',
    'level': 'INFO',
    'dbname': env.cr.dbname,
    'message': '\n'.join(msgs),
    'func': '',
    'path': '',
    'line': '',
})
