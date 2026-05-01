CREATE OR REPLACE FUNCTION public.fn_create_chat_session(p_name text DEFAULT 'New Chat'::text, p_agent_id integer DEFAULT NULL::integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx     t_request_context;
  v_session jsonb;
  v_id      integer;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_create_chat_session');

    INSERT INTO public.chat_sessions (name, agent_id, tenant_id, created_by, updated_by, is_active)
    VALUES (
      COALESCE(NULLIF(trim(p_name), ''), 'New Chat'),
      p_agent_id,
      v_ctx.tenant_id,
      v_ctx.user_id,
      v_ctx.user_id,
      true
    )
    RETURNING id INTO v_id;

    SELECT to_jsonb(t) INTO v_session
    FROM (
      SELECT s.id, s.name, s.agent_id, s.created_at
      FROM   public.chat_sessions s
      WHERE  s.id = v_id
    ) t;

    RETURN fn_response_success(
      p_data          := jsonb_build_array(v_session),
      p_message       := 'Chat session created',
      p_total_records := 1,
      p_page_size     := 1,
      p_page_index    := 1
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error(
      p_function_name := 'fn_create_chat_session',
      p_message       := SQLERRM,
      p_data          := '[]'::jsonb,
      p_tenant_id     := v_ctx.tenant_id,
      p_user_id       := v_ctx.user_id
    );
  END;
END;
$function$
