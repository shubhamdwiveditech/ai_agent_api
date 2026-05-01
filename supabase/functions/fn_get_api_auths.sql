CREATE OR REPLACE FUNCTION public.fn_get_api_auths(p_id integer DEFAULT NULL::integer, p_search text DEFAULT NULL::text)
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
    v_ctx := fn_get_request_context('fn_get_api_auths');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO v_result
    FROM (
      SELECT
        a.id, a.name, a.description, a.auth_type,
        a.username, a.password, a.auth_url, a.auth_method, a.auth_payload,
        a.token_field_path,
        COALESCE(a.headers, '{}'::jsonb) AS headers,
        COALESCE(a.data, '{}'::jsonb) AS data,
        COALESCE(a.metadata, '{}'::jsonb) AS metadata,
        COALESCE(a.access_control, '{}'::jsonb) AS access_control,
        a.created_at, a.updated_at,
        COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name) ORDER BY r.name)
          FROM public.roles r
          WHERE r.tenant_id = v_ctx.tenant_id
            AND COALESCE(r.is_active, true) = true
            AND r.id::text = ANY (
              SELECT jsonb_array_elements_text(COALESCE(a.access_control->'roles', '[]'::jsonb))
            )
        ), '[]'::jsonb) AS roles
      FROM public.api_auths a
      WHERE a.tenant_id = v_ctx.tenant_id
        AND COALESCE(a.is_active, true) = true
        AND (p_id IS NULL OR a.id = p_id)
        AND (
          p_search IS NULL OR p_search = ''
          OR a.name ILIKE '%' || p_search || '%'
          OR a.description ILIKE '%' || p_search || '%'
        )
      ORDER BY a.id DESC
    ) t;

    RETURN fn_response_success(
      p_data := v_result,
      p_message := 'API credentials retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_api_auths', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
