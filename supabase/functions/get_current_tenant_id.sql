CREATE OR REPLACE FUNCTION public.get_current_tenant_id()
 RETURNS integer
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    v_tenant_id INTEGER;
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM fn_get_request_context('get_current_tenant_id');
    RETURN v_tenant_id;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$function$
