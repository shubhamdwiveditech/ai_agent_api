CREATE OR REPLACE FUNCTION public.fn_save_chat(
    p_session_id  INTEGER  DEFAULT NULL,
    p_role        TEXT     DEFAULT 'user',
    p_content     TEXT     DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_ctx t_request_context;
    v_id  INTEGER;
BEGIN
    BEGIN
        v_ctx := fn_get_request_context('fn_save_chat');

        IF p_session_id IS NULL OR p_session_id = 0 THEN
            RAISE EXCEPTION 'Session ID is required';
        END IF;

        IF p_content IS NULL OR length(trim(p_content)) = 0 THEN
            RAISE EXCEPTION 'Content is required';
        END IF;

        IF lower(coalesce(p_role, '')) NOT IN ('user', 'assistant', 'system') THEN
            RAISE EXCEPTION 'Invalid role. Must be user, assistant or system';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE id = p_session_id
              AND tenant_id = v_ctx.tenant_id
        ) THEN
            RAISE EXCEPTION 'Session not found or access denied';
        END IF;

        INSERT INTO public.chats (
            session_id,
            role,
            content,
            tenant_id,
            is_active,
            created_by,
            created_at
        ) VALUES (
            p_session_id,
            lower(p_role),
            trim(p_content),
            v_ctx.tenant_id,
            true,
            v_ctx.user_id,
            NOW()
        ) RETURNING id INTO v_id;

        RETURN fn_response_success(
            jsonb_build_array(jsonb_build_object('id', v_id)),
            'Chat created successfully'
        );

    EXCEPTION WHEN OTHERS THEN
        RETURN fn_response_error('fn_save_chat', SQLERRM, '[]'::JSONB, v_ctx.tenant_id, v_ctx.user_id);
    END;
END;
$function$