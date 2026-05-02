CREATE OR REPLACE FUNCTION public.fn_get_agent_full(p_agent_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi (enhanced)
Description   : Public API endpoint for agent config.
                Resolves JWT context then delegates
                all data assembly to fn_get_agent_config.

SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
SELECT fn_get_agent_full(1);
================================================
*/
DECLARE
    v_tenant_id  INTEGER;
    v_user_id    INTEGER;
    v_caller_id  INTEGER;
    v_config     JSONB;
BEGIN
    BEGIN
        SELECT tenant_id, user_id, caller_id
        INTO v_tenant_id, v_user_id, v_caller_id
        FROM fn_get_request_context('fn_get_agent_full');

        v_config := fn_get_agent_config(
            p_agent_id  := p_agent_id,
            p_tenant_id := v_tenant_id,
            p_user_id   := v_user_id 
        );

        IF v_config IS NULL THEN
            RETURN fn_response_error(
                p_function_name := 'fn_get_agent_full',
                p_message       := 'Agent not found',
                p_status_code   := 404
            );
        END IF;

        RETURN fn_response_success(
            p_data          := jsonb_build_array(v_config),
            p_message       := 'Agent fetched successfully',
            p_total_records := 1,
            p_page_size     := 1,
            p_page_index    := 1
        );

    EXCEPTION
        WHEN OTHERS THEN
            RETURN fn_response_error(
                p_function_name := 'fn_get_agent_full',
                p_message       := SQLERRM,
                p_data          := '[]'::JSONB,
                p_tenant_id     := v_tenant_id,
                p_user_id       := v_user_id
            );
    END;
END;
$function$
