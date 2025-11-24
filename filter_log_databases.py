"""
Odoo log filter by database.
Handles multi-line logs including tracebacks correctly.

OPW-5244546
"""

import re
import sys
import argparse
from pathlib import Path


def extract_database_name(line):
    """
    Extract database name from a log line.
    Expected format: YYYY-MM-DD HH:MM:SS,mmm PID LEVEL DATABASE ...
    """
    pattern = r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}\s+\d+\s+\w+\s+(\S+)'
    match = re.match(pattern, line)
    return match.group(1) if match else None


def is_log_start(line):
    """
    Check if a line is the start of a new log entry.
    """
    pattern = r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}\s+\d+\s+\w+'
    return bool(re.match(pattern, line))


def get_available_databases(log_file):
    """
    Scan log file and return all databases found.
    """
    databases = set()
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if is_log_start(line):
                db_name = extract_database_name(line)
                if db_name:
                    databases.add(db_name)
    
    return sorted(databases)


def filter_logs_by_database(input_file, output_file, target_db):
    """
    Filter logs and save only those from the specified database.
    Correctly handles multi-line logs and tracebacks.
    """
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:
        
        current_db = None
        capturing = False
        lines_written = 0
        
        for line in infile:
            # If it's the start of a new log entry
            if is_log_start(line):
                current_db = extract_database_name(line)
                capturing = (current_db == target_db)
                
                if capturing:
                    outfile.write(line)
                    lines_written += 1
            
            # If it's not a log start, it's a continuation (traceback or other line)
            elif capturing:
                outfile.write(line)
                lines_written += 1
        
        return lines_written


def main():
    parser = argparse.ArgumentParser(
        description='Filter Odoo logs by database name',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i odoo.log -o vysion.log -d vysion1
  %(prog)s --input logs/odoo.log --output logs/filtered.log --database perennialle
        """
    )
    
    parser.add_argument('-i', '--input', 
                        required=True,
                        help='Input log file path')
    
    parser.add_argument('-o', '--output',
                        required=True,
                        help='Output log file path')
    
    parser.add_argument('-d', '--database',
                        required=True,
                        help='Database name to filter')
    
    parser.add_argument('-l', '--list',
                        action='store_true',
                        help='List available databases and exit')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not Path(args.input).exists():
        print(f"Error: Input file '{args.input}' does not exist.")
        sys.exit(1)
    
    # List databases if requested
    if args.list:
        print(f"Scanning databases in: {args.input}")
        databases = get_available_databases(args.input)
        
        if not databases:
            print("No databases found in log file.")
            sys.exit(1)
        
        print(f"\nFound {len(databases)} database(s):")
        for db in databases:
            print(f"  - {db}")
        sys.exit(0)
    
    # Get available databases to verify target exists
    databases = get_available_databases(args.input)
    
    if not databases:
        print("Error: No databases found in log file.")
        sys.exit(1)
    
    if args.database not in databases:
        print(f"Error: Database '{args.database}' not found in logs.")
        print(f"\nAvailable databases:")
        for db in databases:
            print(f"  - {db}")
        sys.exit(1)
    
    # Filter logs
    print(f"Filtering logs from database: {args.database}")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    
    lines_written = filter_logs_by_database(args.input, args.output, args.database)
    
    print(f"\nSuccess! Wrote {lines_written} lines to output file.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
