CREATE OR REPLACE FUNCTION public.fn_get_agent_config(p_agent_id integer, p_tenant_id integer, p_user_id integer, p_depth integer DEFAULT 0, p_max_depth integer DEFAULT 5)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi (enhanced)
Description   : Recursive agent config resolver.
                Called by fn_get_agent_full.
                p_user_id is reserved for future
                user-level access control (ULAC).
                p_depth / p_max_depth prevent
                circular-reference stack overflows.
================================================
*/
DECLARE
    v_agent      RECORD;
    v_sub_agents JSONB;
    v_result     JSONB;
    v_vars       JSONB;
    v_analytics_tools JSONB DEFAULT '[]'::JSONB;
BEGIN
    -- Depth-limit guard
    IF p_depth > p_max_depth THEN
        RETURN jsonb_build_object(
            'error',    'Max recursion depth reached',
            'agent_id', p_agent_id
        );
    END IF;


    -- ── 1. Build variable map for this tenant ────────────────────
    v_vars := public.fn_get_variable_map(p_tenant_id, p_user_id);

    -- Fetch the agent row
    SELECT a.*, l.provider INTO v_agent
    FROM agents a inner join llm_configs l
    on a.llm_config_id = l.id
    WHERE a.id        = p_agent_id
      AND a.tenant_id = p_tenant_id;
      -- TODO: add user-level access check here when ULAC is implemented
      -- e.g. AND EXISTS (SELECT 1 FROM agent_permissions WHERE agent_id = p_agent_id AND user_id = p_user_id)

    IF v_agent IS NULL THEN
        RETURN NULL;
    END IF;

    -- ── Get Analytics tools for text to sql ──────────────────────────────────
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'id',              ds.id,
                'name',            ds.name,
                'api_type',        ds.api_type,
                'method',          ds.method,
                'url',             fn_resolve_variables(ds.url,          v_vars),
                'body',            fn_resolve_variables(ds.body::TEXT,    v_vars),
                'headers',         fn_resolve_variables(ds.headers::TEXT, v_vars)::JSONB,
                'fields',          ds.fields,
                'data_field_path', ds.data_field_path,
                'api_auth_id',     ds.api_auth_id
            ))), '[]'::JSONB
    INTO v_analytics_tools
    FROM api_config ds
    WHERE ds.id        = ANY(v_agent.tool_ids)
      AND ds.is_active = true
      AND ds.api_type  = 'analytics'
      AND ds.tenant_id = p_tenant_id;
              
    -- ── Resolve sub_agents recursively ──────────────────────────────────
    v_sub_agents := '[]'::JSONB;

    IF v_agent.data ? 'sub_agents'
       AND jsonb_array_length(v_agent.data->'sub_agents') > 0
    THEN
        SELECT jsonb_agg(
            sub_config.config || jsonb_build_object('priority', (entry.value->>'priority')::INTEGER)
            ORDER BY (entry.value->>'priority')::INTEGER
        )
        INTO v_sub_agents
        FROM jsonb_array_elements(v_agent.data->'sub_agents') AS entry(value)
        CROSS JOIN LATERAL (
            SELECT fn_get_agent_config(
                (entry.value->>'id')::INTEGER,
                p_tenant_id,
                p_user_id, 
                p_depth + 1,
                p_max_depth
            ) AS config
        ) AS sub_config
        WHERE sub_config.config IS NOT NULL;
    END IF;

    -- ── Build the full agent object ──────────────────────────────────────
    SELECT jsonb_build_object(
        'id',            v_agent.id,
        'tenant_id',            v_agent.tenant_id,
        'name',          v_agent.name,
        'description',   v_agent.description,
        'system_prompt', v_agent.system_prompt,
        'is_active',     v_agent.is_active,
        'avatar',        v_agent.avatar,
        'data',          v_agent.data,
        'llm_config_id' , v_agent.llm_config_id,
        'llm_provider' , v_agent.provider,
        'tool_ids' , v_agent.tool_ids,
        'analytics_tools', v_analytics_tools,
        'sub_agents',    COALESCE(v_sub_agents, '[]'::JSONB),
        'knowledge_bases', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id',          kb.id,
                'name',        kb.name,
                'description', kb.description
            ))
            FROM knowledge_bases kb
            WHERE kb.id        = ANY(v_agent.kb_ids)
              AND kb.is_active = true
              AND kb.tenant_id = p_tenant_id
        ), '[]'::JSONB),
        'tools', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id',              ds.id,
                'name',            ds.name,
                'api_type',        ds.api_type,
                'method',          ds.method,
                'url',             fn_resolve_variables(ds.url,          v_vars),
                'body',            fn_resolve_variables(ds.body::TEXT,    v_vars),
                'headers',         fn_resolve_variables(ds.headers::TEXT, v_vars)::JSONB,
                'fields',          ds.fields,
                'data_field_path', ds.data_field_path,
                'api_auth_id',     ds.api_auth_id
            ))
            FROM api_config ds
            WHERE ds.id        = ANY(v_agent.tool_ids)
              AND ds.is_active = true
              AND ds.api_type = 'action'
              AND ds.tenant_id = p_tenant_id
        ), '[]'::JSONB)

    ) INTO v_result;

    RETURN v_result;
END;
$function$
