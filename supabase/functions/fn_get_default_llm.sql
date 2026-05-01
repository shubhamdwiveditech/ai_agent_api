CREATE OR REPLACE FUNCTION public.fn_get_default_llm()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
====================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi
Modified Date : 01-May-2026
Description   : Get Default LLM for embed and chat in not selected
====================================================
SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
select fn_get_default_llm()
*/
DECLARE
  v_ctx        t_request_context;
  v_result     jsonb;
  v_chat       jsonb;
  v_embed      jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_get_default_llm');

    -- Chat model: default config where embed mode is NOT set
    SELECT to_jsonb(t)
    INTO   v_chat
    FROM (
      SELECT
        l.provider,
        l.model,
        l.api_key,
        l.endpoint
      FROM public.llm_configs l
      WHERE l.is_default  = true
        AND l.tenant_id   = v_ctx.tenant_id
        AND (l.data->>'is_embed_model' IS NULL
          OR l.data->>'is_embed_model' = 'false')
      LIMIT 1
    ) t;

    -- Embed model: default config where embed mode IS true
    SELECT to_jsonb(t)
    INTO   v_embed
    FROM (
      SELECT
        l.provider,
        l.model,
        l.api_key,
        l.endpoint
      FROM public.llm_configs l
      WHERE l.is_default              = true
        AND l.tenant_id               = v_ctx.tenant_id
        AND l.data->>'is_embed_model'  = 'true'
      LIMIT 1
    ) t;

    -- Combine into a single object
    v_result := jsonb_build_object(
      'chat_model',  v_chat,
      'embed_model', v_embed
    );

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Default LLM configs retrieved',
      p_total_records := 1
    );

  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error(
      'fn_get_default_llm',
      SQLERRM,
      '[]'::jsonb,
      v_ctx.tenant_id,
      v_ctx.user_id
    );
  END;
END;
$function$
