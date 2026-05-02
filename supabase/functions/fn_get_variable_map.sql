CREATE OR REPLACE FUNCTION public.fn_get_variable_map(p_tenant_id integer, p_user_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    v_result     JSONB;
    v_user_email TEXT;
BEGIN
    -- Get user email
    SELECT email
    INTO v_user_email
    FROM profiles
    WHERE tenant_id = p_tenant_id
      AND id        = p_user_id
      AND is_active = true;

    -- Build variable map, overriding SYS_USER_EMAIL value if it exists
    SELECT COALESCE(
        jsonb_object_agg(
            v.name,
            CASE 
                WHEN v.name = 'SYS_USER_EMAIL' THEN v_user_email
                ELSE v.value
            END
        ),
        '{}'::JSONB
    )
    INTO v_result
    FROM global_variables v
    WHERE v.tenant_id in ( p_tenant_id, 0)
      AND v.is_active = true;

    RETURN v_result;
END;
$function$
