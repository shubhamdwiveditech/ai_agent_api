CREATE OR REPLACE FUNCTION public.fn_get_api_configs(p_id integer DEFAULT NULL::integer, p_search text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
  v_result jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_get_api_configs');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO v_result
    FROM (
      SELECT
        c.id, c.api_type, c.name, c.url, c.method,
        COALESCE(c.headers, '{}'::jsonb) AS headers,
        c.body,
        COALESCE(c.fields, '[]'::jsonb) AS fields,
        c.api_auth_id,
        c.data_field_path,
        COALESCE(c.data, '{}'::jsonb) AS data,
        COALESCE(c.metadata, '{}'::jsonb) AS metadata,
        COALESCE(c.access_control, '{}'::jsonb) AS access_control,
        c.created_at, c.updated_at,
        (SELECT a.name FROM public.api_auths a WHERE a.id = c.api_auth_id) AS api_auth_name,
        (SELECT a.auth_type FROM public.api_auths a WHERE a.id = c.api_auth_id) AS api_auth_type,
        COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name) ORDER BY r.name)
          FROM public.roles r
          WHERE r.tenant_id = v_ctx.tenant_id
            AND COALESCE(r.is_active, true) = true
            AND r.id::text = ANY (
              SELECT jsonb_array_elements_text(COALESCE(c.access_control->'roles', '[]'::jsonb))
            )
        ), '[]'::jsonb) AS roles
      FROM public.api_config c
      WHERE c.tenant_id = v_ctx.tenant_id
        AND COALESCE(c.is_active, true) = true
        AND (p_id IS NULL OR c.id = p_id)
        AND (
          p_search IS NULL OR p_search = ''
          OR c.name ILIKE '%' || p_search || '%'
          OR c.url ILIKE '%' || p_search || '%'
        )
      ORDER BY c.id DESC
    ) t;

    RETURN fn_response_success(
      p_data := v_result,
      p_message := 'API configs retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_api_configs', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
