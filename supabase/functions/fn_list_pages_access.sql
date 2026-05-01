CREATE OR REPLACE FUNCTION public.fn_list_pages_access(p_search text DEFAULT NULL::text)
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
    v_ctx := fn_get_request_context('fn_list_pages_access');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'module_name'), (to_jsonb(t)->>'name')), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT
        p.id,
        m.name        AS module_name,
        p.name        AS name,
        p.descr       AS descr,
        p.route_name  AS route_name,
        COALESCE(p.access_control, '{}'::jsonb) AS access_control,
        COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name) ORDER BY r.name)
          FROM   public.roles r
          WHERE  r.tenant_id = v_ctx.tenant_id
            AND  COALESCE(r.is_active, true) = true
            AND  r.id::text = ANY (
              SELECT jsonb_array_elements_text(COALESCE(p.access_control->'roles', '[]'::jsonb))
            )
        ), '[]'::jsonb) AS roles
      FROM public.pages p
      INNER JOIN public.modules m ON m.id = p.module_id
      WHERE COALESCE(p.is_active, true) = true
        AND (p.tenant_id IS NULL OR p.tenant_id = v_ctx.tenant_id)
        AND (
          p_search IS NULL OR p_search = ''
          OR p.name   ILIKE '%' || p_search || '%'
          OR p.descr  ILIKE '%' || p_search || '%'
          OR m.name   ILIKE '%' || p_search || '%'
        )
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Pages retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_list_pages_access', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
