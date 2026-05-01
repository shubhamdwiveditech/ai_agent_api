CREATE OR REPLACE FUNCTION public.fn_list_chat_messages(p_session_id integer)
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
    v_ctx := fn_get_request_context('fn_list_chat_messages');

    IF NOT EXISTS (
      SELECT 1 FROM public.chat_sessions
      WHERE id = p_session_id
        AND tenant_id  = v_ctx.tenant_id
        AND created_by = v_ctx.user_id
    ) THEN
      RAISE EXCEPTION 'Chat session not found or access denied';
    END IF;

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT c.id,
             c.role,
             c.content,
             c.created_at,
             COALESCE(c.data->'sources', '[]'::jsonb) AS sources
      FROM   public.chats c
      WHERE  c.session_id = p_session_id
        AND  COALESCE(c.is_active, true) = true
      ORDER BY c.id ASC
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Chat messages retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error(
      p_function_name := 'fn_list_chat_messages',
      p_message       := SQLERRM,
      p_data          := '[]'::jsonb,
      p_tenant_id     := v_ctx.tenant_id,
      p_user_id       := v_ctx.user_id
    );
  END;
END;
$function$
