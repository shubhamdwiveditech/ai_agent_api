CREATE OR REPLACE FUNCTION public.fn_get_mcp_tools()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi
Description   : Get list of API for MCP tool list

SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
SELECT fn_get_mcp_tools();
================================================
*/
DECLARE
    v_vars  JSONB;
    v_ctx   t_request_context;
    v_tools JSONB DEFAULT '[]'::JSONB;
BEGIN

    BEGIN

        -- ── 1. Resolve request context (tenant + user from JWT) ──────
        v_ctx := fn_get_request_context('fn_get_mcp_tools');

        -- ── 2. Build variable map for this tenant ────────────────────
        v_vars := public.fn_get_variable_map(v_ctx.tenant_id, v_ctx.user_id);  

        -- ── 3. Fetch active tools for tenant ─────────────────────────
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'id',              ds.id,
                'name',            ds.name,
                'data',        ds.data,
                'api_type',        ds.api_type,
                'method',          ds.method,
                'url',             fn_resolve_variables(ds.url,           v_vars),
                'body',            fn_resolve_variables(ds.body::TEXT,    v_vars),
                'headers',         fn_resolve_variables(ds.headers::TEXT, v_vars)::JSONB,
                'fields',          ds.fields,
                'data_field_path', ds.data_field_path,
                'api_auth_id',     ds.api_auth_id
            )), '[]'::JSONB)
        INTO v_tools
        FROM api_config ds
        WHERE ds.is_active  = true
          AND ds.tenant_id  = v_ctx.tenant_id;  

        RETURN fn_response_success(
            p_data          := v_tools,
            p_message       := 'MCP Tools fetched successfully',
            p_total_records := 1,
            p_page_size     := 1,
            p_page_index    := 1
        );

    EXCEPTION
        WHEN OTHERS THEN
            RETURN fn_response_error(
                p_function_name := 'fn_get_mcp_tools',
                p_message       := SQLERRM,
                p_data          := '[]'::JSONB,
                p_tenant_id     := v_ctx.tenant_id, 
                p_user_id       := v_ctx.user_id  
            );
    END; 

END;
$function$