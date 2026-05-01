CREATE OR REPLACE FUNCTION public.fn_save_chat_message(p_session_id integer, p_role text, p_content text, p_sources jsonb DEFAULT NULL::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx     t_request_context;
  v_message jsonb;
  v_id      integer;
  v_data    jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_chat_message');

    IF p_role NOT IN ('user', 'assistant', 'system') THEN
      RAISE EXCEPTION 'Invalid role: %', p_role;
    END IF;

    IF p_content IS NULL OR length(trim(p_content)) = 0 THEN
      RAISE EXCEPTION 'Message content is required';
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM public.chat_sessions
      WHERE id = p_session_id
        AND tenant_id  = v_ctx.tenant_id
        AND created_by = v_ctx.user_id
    ) THEN
      RAISE EXCEPTION 'Chat session not found or access denied';
    END IF;

    v_data := '{}'::jsonb;
    IF p_sources IS NOT NULL AND jsonb_typeof(p_sources) = 'array' THEN
      v_data := jsonb_build_object('sources', p_sources);
    END IF;

    INSERT INTO public.chats (session_id, role, content, tenant_id, created_by, updated_by, is_active, data)
    VALUES (p_session_id, p_role, p_content, v_ctx.tenant_id, v_ctx.user_id, v_ctx.user_id, true, v_data)
    RETURNING id INTO v_id;

    UPDATE public.chat_sessions
       SET updated_at = now(),
           updated_by = v_ctx.user_id
     WHERE id = p_session_id;

    SELECT to_jsonb(t) INTO v_message
    FROM (
      SELECT c.id, c.role, c.content, c.created_at, c.data
      FROM   public.chats c
      WHERE  c.id = v_id
    ) t;

    RETURN fn_response_success(
      p_data          := jsonb_build_array(v_message),
      p_message       := 'Message saved',
      p_total_records := 1
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error(
      p_function_name := 'fn_save_chat_message',
      p_message       := SQLERRM,
      p_data          := '[]'::jsonb,
      p_tenant_id     := v_ctx.tenant_id,
      p_user_id       := v_ctx.user_id
    );
  END;
END;
$function$
