CREATE OR REPLACE FUNCTION public.fn_set_kb_item_status(p_id integer, p_status text, p_error text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_set_kb_item_status');

    IF p_status NOT IN ('pending', 'processing', 'ready', 'failed') THEN
      RAISE EXCEPTION 'Invalid status: %', p_status;
    END IF;

    UPDATE public.knowledge_base_items
       SET embed_status = p_status,
           is_embedded  = (p_status = 'ready'),
           embed_error  = p_error,
           updated_at   = now(),
           updated_by   = v_ctx.user_id
     WHERE id = p_id AND tenant_id = v_ctx.tenant_id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Item not found or access denied';
    END IF;

    RETURN fn_response_success('[]'::jsonb, 'Status updated');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_set_kb_item_status', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
