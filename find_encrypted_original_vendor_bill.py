'''
Find encrypted files in account.moves (original vendor bill)

This script helps when the customer tries to print by batch a Original Vendor bill and gets:

```
PyPDF2.errors.DependencyError: PyCryptodome is required for AES algorithm
```

OPW-5900263
'''


from PyPDF2 import PdfFileReader

def review_encrypted_vendor_bills(account_moves=[]):
    report_xml = 'account.action_account_original_vendor_bill'
    report_model = env['ir.actions.report']

    encrypted_moves = []
    problematic_moves = []
    total = len(account_moves)

    print("="*60)
    print("PDF ENCRYPTION/MERGE ISSUE DETECTION")
    print("="*60)
    print("")

    for idx, move_id in enumerate(account_moves, 1):
        # Progress loader
        percentage = (idx / total) * 100
        print(f"Progress: {idx}/{total} ({percentage:.1f}%) - Processing move #{move_id}")
        
        try:
            # Generate individual PDF
            collected_streams = report_model._render_qweb_pdf_prepare_streams(report_xml, {}, res_ids=[move_id])
            
            for stream_data in collected_streams.values():
                if stream_data.get('stream'):
                    stream = stream_data['stream']
                    stream.seek(0)
                    
                    try:
                        # Try to read PDF
                        pdf_reader = PdfFileReader(stream)
                        
                        # Check if encrypted
                        if pdf_reader.isEncrypted:
                            encrypted_moves.append(move_id)
                            print(f"  ⚠️  ENCRYPTED PDF DETECTED!")
                            break
                            
                    except Exception as e:
                        print(e)
                        if 'AES' in str(e) or 'PyCryptodome' in str(e) or 'encrypt' in str(e).lower():
                            encrypted_moves.append(move_id)
                            print(f"  ⚠️  AES ENCRYPTION ERROR DETECTED!")
                            break
                    finally:
                        stream.close()
                        
        except Exception as e:
            problematic_moves.append((move_id, str(e)[:100]))
            print(f"  ❌ ERROR: {str(e)[:80]}")

    print("")
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print("")
    print(f"Total moves tested: {total}")
    print(f"Encrypted/AES PDFs: {len(encrypted_moves)}")
    print(f"Other errors: {len(problematic_moves)}")
    print("")

    if encrypted_moves:
        print("ENCRYPTED MOVES (will fail on merge):")
        print("")
        for move_id in encrypted_moves:
            move = env['account.move'].browse(move_id)
            print(f"  - {move.name} (#{move_id})")
        print("")
        print(f"Encrypted IDs: {encrypted_moves}")
        print("")

    if problematic_moves:
        print("OTHER PROBLEMATIC MOVES:")
        print("")
        for move_id, error in problematic_moves:
            move = env['account.move'].browse(move_id)
            print(f"  - {move.name} (#{move_id}): {error}")
