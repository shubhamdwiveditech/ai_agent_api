CREATE OR REPLACE FUNCTION public.fn_get_global_variables(p_id integer DEFAULT NULL::integer, p_search text DEFAULT NULL::text)
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
    v_ctx := fn_get_request_context('fn_get_global_variables');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT
        g.id, g.name, g.value, g.description, g.type,
        COALESCE(g.access_control, '{}'::jsonb) AS access_control,
        g.created_at, g.updated_at,
        COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name) ORDER BY r.name)
          FROM   public.roles r
          WHERE  r.tenant_id = v_ctx.tenant_id
            AND  COALESCE(r.is_active, true) = true
            AND  r.id::text = ANY (
              SELECT jsonb_array_elements_text(COALESCE(g.access_control->'roles', '[]'::jsonb))
            )
        ), '[]'::jsonb) AS roles
      FROM public.global_variables g
      WHERE g.tenant_id = v_ctx.tenant_id
        AND COALESCE(g.is_active, true) = true
        AND (p_id IS NULL OR g.id = p_id)
        AND (
          p_search IS NULL OR p_search = ''
          OR g.name        ILIKE '%' || p_search || '%'
          OR g.description ILIKE '%' || p_search || '%'
        )
      ORDER BY g.id DESC
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Global variables retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_global_variables', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
