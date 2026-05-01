CREATE OR REPLACE FUNCTION public.execute_query(query text)
 RETURNS json
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    result json;
    clean_query text;
BEGIN
    -- Remove trailing semicolon if present
    clean_query := regexp_replace(trim(query), ';$', '');   
    EXECUTE 'SELECT json_agg(t) FROM (' || clean_query || ') t' INTO result;
    RETURN COALESCE(result, '[]'::json);
END;
$function$
