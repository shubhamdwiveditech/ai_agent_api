CREATE OR REPLACE FUNCTION public.fn_get_roles(p_id integer DEFAULT NULL::integer, p_search text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx    t_request_context;
  v_result jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_get_roles');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT r.id, r.name, r.descr, r.access_control, r.created_at, r.updated_at
      FROM   public.roles r
      WHERE  r.tenant_id = v_ctx.tenant_id
        AND  COALESCE(r.is_active, true) = true
        AND  (p_id IS NULL OR r.id = p_id)
        AND  (p_search IS NULL OR p_search = '' OR r.name ILIKE '%' || p_search || '%')
      ORDER BY r.id DESC
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Roles retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_roles', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
