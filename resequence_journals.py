"""
RESEQUENCE JOURNALS

This could fix a unexepected behaviour related to journal incorrect assignation.

Sometimes when you have many custom journals and you move the priority of them (order), 
this can change the behaviour of the ORM query, because the standard order is based on: sequence, type, code.

Imagine you have this scenario:

test => SELECT id, name->>'en_US' name,code, sequence FROM account_journal 
    WHERE type = 'purchase' AND (company_id IN (1) OR company_id IS NULL) ORDER BY sequence,type,code;
 id  |                name                | code  | sequence 
-----+------------------------------------+-------+----------
 111 | Bank                               | INV1  |        5
 113 | Administrative Expenses            | OTROA |        6
  11 | Vendor Bills                       | PROV  |        6

if you create a new Vendor Bill, the function _search_default_journal (18.0) will be called and try to 
search the correct one.

if is not able to choose one, it will do: 

journal = self.env['account.journal'].search(domain, limit=1)

This will choose Bank instead of Vendor Bills, which is incorrect.

We need to ensure that the order is corrrect, and thats the main reason of the existance of this script.


Usage:
just give the journal records to the script and it will do all the necessary... 
multicompany allowed but not expect False company

OPW-5036417
"""

# should be just one type/company priority... it could work but lifo is applied
def resequence_journals(priority_records):
    
    # group records to order by company
    grouped_records = env['account.journal']._read_group(
        domain=[('id', 'in', priority_records.ids)],
        groupby=['type', 'company_id']
    )
    
    for j_type, company_id in grouped_records:
        priority_records_on_group = priority_records.filtered_domain([
            ('type', '=', j_type),
            ('company_id', '=', company_id.id)
        ])
        # make a temporal sequence based on type, code, id (exclude the prority ones)
        env.cr.execute(
            """
            WITH new_sequence AS (
                SELECT id, code,
                ROW_NUMBER() OVER (
                    ORDER BY sequence, type, code
                ) new_sequence
                FROM account_journal 
                WHERE company_id=%s AND type=%s AND id NOT IN %s
            )
            UPDATE account_journal
            SET sequence = ns.new_sequence
            FROM new_sequence ns
            WHERE ns.id=account_journal.id
            RETURNING account_journal.id
            """,
            [company_id.id, j_type, tuple(priority_records_on_group.ids)]
        )
        
        # lambda not valid on scheduled actions... sorry
        def _get_first(x):
            return x[0]
        
        updated_seq_ids = tuple(map(_get_first, env.cr.fetchall()))
        
        # get the major one
        major_journal = env['account.journal'].search([], limit=len(priority_records_on_group))
        if major_journal == priority_records_on_group:
            _logger.info("records has the priority, not needed resequence")
            _logger.info(major_journal.mapped('name'))
            _logger.info(major_journal.mapped('company_id.name'))
            continue
        elif priority_records_on_group in major_journal:
            _logger.info("some records has priority but not all of them")
            priority_records_on_group -= major_journal
        
        # we need to create a space to add our priority values
        from_seq = min(major_journal.mapped('sequence')) 
        to_seq = from_seq + len(priority_records_on_group) + 1
        
        env.cr.execute("""
        UPDATE account_journal
        SET sequence=sequence+%s
        WHERE id IN %s AND id NOT in %s AND sequence >= %s
        """, [
            len(priority_records_on_group),
            updated_seq_ids,
            tuple(priority_records_on_group.ids),
            from_seq
        ])
        # with the space, we can add now the values
        for sequence, priority_record in zip(range(from_seq, to_seq), priority_records_on_group):
            priority_record.write({'sequence': sequence})
        env.cr.commit()
