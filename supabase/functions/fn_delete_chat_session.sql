CREATE OR REPLACE FUNCTION public.fn_delete_chat_session(p_session_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_delete_chat_session');

    IF NOT EXISTS (
      SELECT 1 FROM public.chat_sessions
      WHERE id = p_session_id
        AND tenant_id  = v_ctx.tenant_id
        AND created_by = v_ctx.user_id
    ) THEN
      RAISE EXCEPTION 'Chat session not found or access denied';
    END IF;

    DELETE FROM public.chats         WHERE session_id = p_session_id;
    DELETE FROM public.chat_sessions WHERE id         = p_session_id;

    RETURN fn_response_success(
      p_data    := '[]'::jsonb,
      p_message := 'Chat session deleted'
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error(
      p_function_name := 'fn_delete_chat_session',
      p_message       := SQLERRM,
      p_data          := '[]'::jsonb,
      p_tenant_id     := v_ctx.tenant_id,
      p_user_id       := v_ctx.user_id
    );
  END;
END;
$function$
