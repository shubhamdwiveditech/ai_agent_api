CREATE OR REPLACE FUNCTION public.fn_delete_kb_item(p_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx          t_request_context;
  v_storage_path text;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_delete_kb_item');

    SELECT storage_path INTO v_storage_path
    FROM public.knowledge_base_items
    WHERE id = p_id AND tenant_id = v_ctx.tenant_id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Item not found or access denied';
    END IF;

    DELETE FROM public.knowledge_base_chunks WHERE item_id = p_id;
    DELETE FROM public.knowledge_base_items  WHERE id      = p_id;

    -- Best-effort storage cleanup (ignore errors)
    IF v_storage_path IS NOT NULL THEN
      BEGIN
        DELETE FROM storage.objects WHERE bucket_id = 'knowledge-base' AND name = v_storage_path;
      EXCEPTION WHEN OTHERS THEN NULL;
      END;
    END IF;

    RETURN fn_response_success('[]'::jsonb, 'Item deleted');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_delete_kb_item', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
