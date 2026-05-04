create or replace function public.fn_get_agents (
  p_id integer default null::integer,
  p_search text default null::text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
set
  search_path to 'public' as $function$
DECLARE
  v_ctx t_request_context;
  v_result jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_get_agents');
    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO v_result
    FROM (
      SELECT a.id, a.name, a.description, a.system_prompt, a.llm_config_id,
             a.tool_ids, a.kb_ids, a.avatar, a.agent_type, a.max_iterations,
             a.data, a.metadata, a.access_control, a.is_active, a.created_at, a.updated_at,
             (SELECT jsonb_build_object('id', l.id, 'name', l.name, 'model', l.model)
                FROM public.llm_configs l WHERE l.id = a.llm_config_id) AS llm
      FROM public.agents a
      WHERE a.tenant_id = v_ctx.tenant_id
        AND COALESCE(a.is_active, true) = true
        AND (p_id IS NULL OR a.id = p_id)
        AND (p_search IS NULL OR p_search = '' OR a.name ILIKE '%'||p_search||'%')
      ORDER BY a.id DESC
    ) t;
    RETURN fn_response_success(v_result, 'Agents', 200, COALESCE(jsonb_array_length(v_result),0));
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_agents', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$