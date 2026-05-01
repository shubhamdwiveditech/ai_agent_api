CREATE OR REPLACE FUNCTION public.fn_save_llm_config(p_id integer DEFAULT NULL::integer, p_name text DEFAULT NULL::text, p_provider text DEFAULT NULL::text, p_model text DEFAULT NULL::text, p_api_key text DEFAULT NULL::text, p_endpoint text DEFAULT NULL::text, p_is_default boolean DEFAULT false, p_data jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx  t_request_context;
  v_id   integer;
  v_row  jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_llm_config');

    IF v_ctx.tenant_id IS NULL THEN
      RAISE EXCEPTION 'No tenant context';
    END IF;

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;

    IF p_provider IS NULL OR length(trim(p_provider)) = 0 THEN
      RAISE EXCEPTION 'Provider is required';
    END IF;

    IF p_model IS NULL OR length(trim(p_model)) = 0 THEN
      RAISE EXCEPTION 'Model is required';
    END IF;

    -- Clear existing default before setting a new one
    IF p_is_default = true THEN
      UPDATE llm_configs
         SET is_default = false
       WHERE tenant_id = v_ctx.tenant_id
         AND (p_id IS NULL OR id <> p_id);
    END IF;

    IF p_id IS NULL OR p_id = 0 THEN
      INSERT INTO llm_configs (
        name, provider, model, api_key, endpoint, is_default, data,
        tenant_id, created_by, created_at, updated_by, updated_at
      ) VALUES (
        trim(p_name), p_provider, p_model, p_api_key, p_endpoint, p_is_default, p_data,
        v_ctx.tenant_id, v_ctx.user_id, now(), v_ctx.user_id, now()
      )
      RETURNING id INTO v_id;
    ELSE
      IF NOT EXISTS (
        SELECT 1 FROM llm_configs
        WHERE id = p_id AND tenant_id = v_ctx.tenant_id
      ) THEN
        RAISE EXCEPTION 'LLM config not found or access denied';
      END IF;

      UPDATE llm_configs
         SET name       = trim(p_name),
             provider   = p_provider,
             model      = p_model,
             api_key    = p_api_key,
             endpoint   = p_endpoint,
             is_default = p_is_default,
             data       = p_data,
             updated_by = v_ctx.user_id,
             updated_at = now()
       WHERE id = p_id AND tenant_id = v_ctx.tenant_id;

      v_id := p_id;
    END IF;

    SELECT to_jsonb(t) INTO v_row
    FROM (
      SELECT id, name, provider, model, endpoint, is_default, data,
             created_at, updated_at
      FROM llm_configs WHERE id = v_id
    ) t;

    RETURN fn_response_success(
      jsonb_build_array(v_row),
      CASE WHEN p_id IS NULL OR p_id = 0 THEN 'LLM config created successfully' ELSE 'LLM config updated successfully' END
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_save_llm_config', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
