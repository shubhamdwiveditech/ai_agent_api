CREATE OR REPLACE FUNCTION public.fn_get_llm_config_for_cache(p_id integer DEFAULT NULL::integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi
Created Date  : 02/May/2026
Description   : Fetch LLM configs for the current
                tenant. api_key is masked — raw
                credentials are never returned.
SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
SELECT fn_get_llm_config_for_cache();
================================================
*/
declare
    v_tenant_id     integer;
    v_user_id       integer;
    v_caller_id     integer;
    v_result        jsonb;
    v_total_records integer;
begin
    begin
        -- ─────────────────────────────────────────
        -- 1. Get request context
        -- ─────────────────────────────────────────
        select tenant_id, user_id, caller_id
        into v_tenant_id, v_user_id, v_caller_id
        from fn_get_request_context('fn_get_llm_config_for_cache');

        -- ─────────────────────────────────────────
        -- 2. Fetch records
        --    raw credentials to the client
        -- ─────────────────────────────────────────
        select
            jsonb_agg(
                jsonb_build_object(
                    'id',             l.id,
                    'name',           l.name,
                    'provider',       l.provider,
                    'model',          l.model,
                    'api_key',        l.api_key,
                    'endpoint',       l.endpoint,
                    'is_default',     l.is_default,
                    'data',           coalesce(l.data,           '{}'),
                    'metadata',       coalesce(l.metadata,       '{}')
                )
                order by l.created_at desc
            ),
            count(*)
        into v_result, v_total_records
        from llm_configs l
        where l.tenant_id = v_tenant_id
          and l.is_active  = true
          and (p_id is null or l.id = p_id);

        -- ─────────────────────────────────────────
        -- 3. Default empty result
        -- ─────────────────────────────────────────
        if v_result is null then
            v_result        := '[]'::jsonb;
            v_total_records := 0;
        end if;

        -- ─────────────────────────────────────────
        -- 4. Return success
        -- ─────────────────────────────────────────
        return fn_response_success(
            p_data          := v_result,
            p_message       := 'LLM Configs fetched successfully',
            p_total_records := v_total_records,
            p_page_size     := v_total_records,
            p_page_index    := 1
        );

    exception
        when others then
            return fn_response_error(
                p_function_name := 'fn_get_llm_config_for_cache',
                p_message       := sqlerrm,
                p_data          := '[]'::jsonb,
                p_tenant_id     := v_tenant_id,
                p_user_id       := v_user_id
            );
    end;
end;
$function$
