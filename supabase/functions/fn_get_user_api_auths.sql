CREATE OR REPLACE FUNCTION public.fn_get_user_api_auths(p_id integer DEFAULT NULL::integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$

/*
================================================
Copyright     : AI App, 2026
Description   : Returns active api_auths for the
                tenant with {{VAR_NAME}} placeholders
                resolved from the variables table.
                Resolves in: auth_url, headers,
                             auth_payload
                p_id = NULL  → all active auths
                p_id = <id>  → single auth by id

SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
SELECT fn_get_user_api_auths();        -- all
SELECT fn_get_user_api_auths(p_id=>2); -- single
================================================

*/

DECLARE

    v_tenant_id  INTEGER;
    v_user_id    INTEGER;
    v_caller_id  INTEGER;
    v_vars       JSONB;
    v_result     JSONB;

BEGIN

    BEGIN

        SELECT tenant_id, user_id, caller_id
        INTO v_tenant_id, v_user_id, v_caller_id
        FROM fn_get_request_context('fn_get_user_api_auths');

        -- ── 1. Build variable map for this tenant ────────────────────
        v_vars := public.fn_get_variable_map(v_tenant_id, v_user_id);
        
        -- ── 2. Fetch auths with placeholders resolved ─────────────────
        SELECT COALESCE(jsonb_agg(
            jsonb_build_object(
                'id',               aa.id,
                'name',             aa.name,
                'description',      aa.description,
                'auth_type',        aa.auth_type,
                'auth_method',      aa.auth_method,
                'auth_url',         fn_resolve_variables(aa.auth_url,        v_vars),
                'auth_payload',     fn_resolve_variables(aa.auth_payload,     v_vars),
                'token_field_path', aa.token_field_path,
                'headers',          fn_resolve_variables(aa.headers::TEXT,    v_vars)::JSONB,
                'username',         aa.username,
                'password',         aa.password
            )
            ORDER BY aa.id

        ), '[]'::JSONB)

        INTO v_result
        FROM api_auths aa
        WHERE aa.tenant_id = v_tenant_id
          AND aa.is_active = true
          AND (p_id IS NULL OR aa.id = p_id);  -- ← optional filter


        -- 404 when fetching by id and nothing matched
        IF p_id IS NOT NULL AND jsonb_array_length(v_result) = 0 THEN
            RETURN fn_response_error(
                p_function_name := 'fn_get_user_api_auths',
                p_message       := 'API auth not found',
                p_status_code   := 404
            );

        END IF;


        RETURN fn_response_success(
            p_data          := v_result,
            p_message       := 'API auths fetched successfully',
            p_total_records := jsonb_array_length(v_result),
            p_page_size     := jsonb_array_length(v_result),
            p_page_index    := 1
        );

    EXCEPTION

        WHEN OTHERS THEN
            RETURN fn_response_error(
                p_function_name := 'fn_get_user_api_auths',
                p_message       := SQLERRM,
                p_data          := '[]'::JSONB,
                p_tenant_id     := v_tenant_id,
                p_user_id       := v_user_id
            );

    END;

END;

$function$
