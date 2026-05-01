CREATE OR REPLACE FUNCTION public.fn_get_user_profiles(p_id integer DEFAULT NULL::integer, p_search text DEFAULT NULL::text)
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
    v_ctx := fn_get_request_context('fn_get_user_profiles');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT
        p.id,
        p.user_id,
        p.email,
        p.user_name,
        p.is_active,
        p.created_at,
        p.updated_at,
        p.access_control,
        COALESCE(p.access_control->'roles', '[]'::jsonb) AS role_ids,
        COALESCE((p.access_control->>'is_admin')::boolean, false) AS is_admin,
        COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', r.id, 'name', r.name)
                           ORDER BY r.name)
          FROM   public.roles r
          WHERE  r.tenant_id = v_ctx.tenant_id
            AND  COALESCE(r.is_active, true) = true
            AND  r.id::text = ANY (
              SELECT jsonb_array_elements_text(COALESCE(p.access_control->'roles', '[]'::jsonb))
            )
        ), '[]'::jsonb) AS roles
      FROM public.profiles p
      WHERE p.tenant_id = v_ctx.tenant_id
        AND COALESCE(p.is_active, true) = true
        AND (p_id IS NULL OR p.id = p_id)
        AND (
          p_search IS NULL OR p_search = ''
          OR p.user_name ILIKE '%' || p_search || '%'
          OR p.email     ILIKE '%' || p_search || '%'
        )
      ORDER BY p.id DESC
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Users retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_user_profiles', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
