CREATE OR REPLACE FUNCTION public.fn_get_vas_services()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi 
Description   : Get VAS Services
================================================
*/
DECLARE
  v_ctx    t_request_context;
  v_result jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_get_vas_services');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT id, name , service_type ,  description ,   data
      FROM   public.vas_services 
      WHERE  tenant_id = v_ctx.tenant_id
      ORDER BY name 
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'VAS services retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_vas_services', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
