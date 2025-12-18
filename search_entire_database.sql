-- SQL FUNCTION TO SEARCH IN THE WHOLE DATABASE... IT MIGHT BE SLOW
-- USEFUL WHEN YOU DONT KNOW WHERE BEGIN YOUR SEARCH
CREATE OR REPLACE FUNCTION search_entire_database(search_term TEXT)
RETURNS TABLE(
    schema_name TEXT,
    table_name TEXT,
    column_name TEXT,
    row_count BIGINT,
    sample_value TEXT
) AS $$
DECLARE
    rec RECORD;
    query TEXT;
    result_count BIGINT;
    sample TEXT;
BEGIN
    -- FOR IN ALL TABLES
    FOR rec IN 
        SELECT 
            t.table_schema,
            t.table_name,
            c.column_name,
            c.data_type
        FROM information_schema.tables t
        JOIN information_schema.columns c 
            ON t.table_schema = c.table_schema 
            AND t.table_name = c.table_name
        WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
            AND t.table_type = 'BASE TABLE'
            -- Solo columnas de texto o convertibles a texto
            AND c.data_type IN ('character varying', 'varchar', 'character', 
                               'char', 'text', 'name', 'json', 'jsonb')
    LOOP
        -- BUILD SEARCH
        query := format(
            'SELECT COUNT(*), MIN(%I::TEXT) 
             FROM %I.%I 
             WHERE %I::TEXT ILIKE %L',
            rec.column_name,
            rec.table_schema,
            rec.table_name,
            rec.column_name,
            '%' || search_term || '%'
        );
        
        BEGIN
            EXECUTE query INTO result_count, sample;
            
            -- RETURN VALUES IF EXISTS
            IF result_count > 0 THEN
                schema_name := rec.table_schema;
                table_name := rec.table_name;
                column_name := rec.column_name;
                row_count := result_count;
                sample_value := sample;
                RETURN NEXT;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            -- IGNORE EXCEPTIONS
            CONTINUE;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- USAGE:
-- SELECT * FROM search_entire_database('search_something');
