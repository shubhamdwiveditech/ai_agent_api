CREATE OR REPLACE FUNCTION public.fn_get_llm_configs(p_id integer DEFAULT NULL::integer, p_search text DEFAULT NULL::text)
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
    v_ctx := fn_get_request_context('fn_get_llm_configs');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT
        l.id,
        l.name,
        l.provider,
        l.model,
        l.api_key,
        l.endpoint,
        l.is_default,
        COALESCE(l.access_control, '{}'::jsonb) AS access_control,
        l.data,
        l.created_at,
        l.updated_at,
        COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name) ORDER BY r.name)
          FROM   public.roles r
          WHERE  r.tenant_id = l.tenant_id
            AND  COALESCE(r.is_active, true) = true
            AND  r.id::text = ANY (
              SELECT jsonb_array_elements_text(COALESCE(l.access_control->'roles', '[]'::jsonb))
            )
        ), '[]'::jsonb) AS roles
      FROM public.llm_configs l
      WHERE l.tenant_id = v_ctx.tenant_id
        AND l.is_active = true
        AND (p_id IS NULL OR l.id = p_id)
        AND (
          p_search IS NULL OR p_search = ''
          OR l.name     ILIKE '%' || p_search || '%'
          OR l.provider ILIKE '%' || p_search || '%'
          OR l.model    ILIKE '%' || p_search || '%'
        )
      ORDER BY l.id DESC
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'LLM configs retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_llm_configs', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
