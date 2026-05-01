CREATE OR REPLACE FUNCTION public.fn_list_chat_sessions(p_search text DEFAULT NULL::text, p_limit integer DEFAULT 200)
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
    v_ctx := fn_get_request_context('fn_list_chat_sessions');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'created_at') DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT s.id, s.name, s.agent_id, s.created_at
      FROM   public.chat_sessions s
      WHERE  s.tenant_id  = v_ctx.tenant_id
        AND  s.created_by = v_ctx.user_id
        AND  COALESCE(s.is_active, true) = true
        AND  (p_search IS NULL OR p_search = '' OR s.name ILIKE '%' || p_search || '%')
      ORDER BY s.created_at DESC
      LIMIT GREATEST(COALESCE(p_limit, 200), 1)
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Chat sessions retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0),
      p_page_size     := COALESCE(p_limit, 200),
      p_page_index    := 1
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error(
      p_function_name := 'fn_list_chat_sessions',
      p_message       := SQLERRM,
      p_data          := '[]'::jsonb,
      p_tenant_id     := v_ctx.tenant_id,
      p_user_id       := v_ctx.user_id
    );
  END;
END;
$function$
