CREATE OR REPLACE FUNCTION public.fn_get_chats(
    p_session_id  INTEGER  DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
/*
====================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi
Modified Date : 02-May-2026
Description   : Create VAS service request
====================================================
SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
select fn_get_chats(12)
*/
DECLARE
    v_ctx  t_request_context;
    v_rows JSONB;
BEGIN
    BEGIN
        v_ctx := fn_get_request_context('fn_get_chats');

        IF p_session_id IS NULL OR p_session_id = 0 THEN
            RAISE EXCEPTION 'Session ID is required';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE id = p_session_id
              AND tenant_id = v_ctx.tenant_id
        ) THEN
            RAISE EXCEPTION 'Session not found or access denied';
        END IF;

        SELECT COALESCE(jsonb_agg(t ORDER BY t.created_at ASC), '[]'::JSONB) INTO v_rows
        FROM (
            SELECT
                c.session_id,
                c.role,
                c.content,
                c.created_at
            FROM public.chats c
            WHERE c.session_id = p_session_id
            AND c.tenant_id  = v_ctx.tenant_id
            AND COALESCE(c.is_active, true) = true
        ) t;
        RETURN fn_response_success(v_rows, 'Chats fetched successfully');

    EXCEPTION WHEN OTHERS THEN
        RETURN fn_response_error('fn_get_chats', SQLERRM, '[]'::JSONB, v_ctx.tenant_id, v_ctx.user_id);
    END;
END;
$function$