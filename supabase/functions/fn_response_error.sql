CREATE OR REPLACE FUNCTION public.fn_response_error(p_function_name text, p_message text, p_data jsonb DEFAULT '[]'::jsonb, p_tenant_id bigint DEFAULT NULL::bigint, p_user_id bigint DEFAULT NULL::bigint)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_safe_message TEXT;
BEGIN
    INSERT INTO public.error_logs (
        function_name, error_message, status_code, data, tenant_id, created_by
    )
    VALUES (
        p_function_name, p_message, 400, p_data, p_tenant_id, p_user_id
    );

    v_safe_message := CASE
        WHEN p_message ILIKE '%duplicate key%' OR p_message ILIKE '%unique%constraint%' THEN 'A record with this value already exists'
        WHEN p_message ILIKE '%not found%' OR p_message ILIKE '%no rows%' THEN 'The requested resource was not found'
        WHEN p_message ILIKE '%foreign key%' THEN 'This record is referenced by other data and cannot be modified'
        WHEN p_message ILIKE '%not null%' OR p_message ILIKE '%is required%' THEN p_message
        WHEN p_message ILIKE '%access denied%' OR p_message ILIKE '%unauthorized%' OR p_message ILIKE '%permission%' THEN 'Access denied'
        WHEN p_message ILIKE '%invalid%' AND (p_message ILIKE '%api key%' OR p_message ILIKE '%authentication%') THEN 'Invalid or inactive credentials'
        WHEN p_message ILIKE '%does not belong%' THEN 'Access denied'
        WHEN p_message ILIKE '%admin%' THEN p_message
        WHEN p_message ILIKE '%deleted successfully%' OR p_message ILIKE '%saved successfully%' OR p_message ILIKE '%created successfully%' OR p_message ILIKE '%updated successfully%' THEN p_message
        ELSE 'An unexpected error occurred. Please try again.'
    END;

    RETURN jsonb_build_object(
        'is_success',   false,
        'data',         p_data,
        'paging',       jsonb_build_object(
                          'total_records', 0,
                          'page_size',     0,
                          'page_index',    0
                        ),
        'message',      v_safe_message,
        'status_code',  400
    );
END;
$function$
