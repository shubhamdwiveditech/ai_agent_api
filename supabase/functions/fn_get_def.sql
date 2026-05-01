CREATE OR REPLACE FUNCTION public.fn_get_def(function_name text)
 RETURNS TABLE(function_definition text)
 LANGUAGE plpgsql
AS $function$
/*
=======================================================
Copyright : BLS, 2026
Created By  : Shubham Dwivedi
Modified Date : 26-Apr-2026
Description : Get function definition
=======================================================
*/
BEGIN
    RETURN QUERY
    SELECT 
       
        pg_get_functiondef(p.oid) AS function_definition
    FROM 
        pg_proc p
    JOIN 
        pg_namespace n ON p.pronamespace = n.oid
    WHERE 
        p.proname = function_name;
END;
$function$
