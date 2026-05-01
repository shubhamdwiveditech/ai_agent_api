CREATE OR REPLACE FUNCTION public.fn_delete_llm_config(p_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_delete_llm_config');

    UPDATE public.llm_configs
       SET is_active = false,
           updated_at = now(),
           updated_by = v_ctx.user_id
     WHERE id = p_id
       AND tenant_id = v_ctx.tenant_id
       AND COALESCE(is_active, true) = true;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'LLM config not found or already deleted';
    END IF;

    RETURN fn_response_success('[]'::jsonb, 'LLM config deleted successfully');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_delete_llm_config', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
