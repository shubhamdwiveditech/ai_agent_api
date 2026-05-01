CREATE OR REPLACE FUNCTION public.fn_save_kb_chunks(p_item_id integer, p_chunks jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx     t_request_context;
  v_kb_id   integer;
  v_count   integer;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_kb_chunks');

    SELECT kb_id INTO v_kb_id
    FROM public.knowledge_base_items
    WHERE id = p_item_id AND tenant_id = v_ctx.tenant_id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Item not found or access denied';
    END IF;

    IF p_chunks IS NULL OR jsonb_typeof(p_chunks) <> 'array' THEN
      RAISE EXCEPTION 'Chunks payload must be a JSON array';
    END IF;

    -- Replace existing chunks for this item
    DELETE FROM public.knowledge_base_chunks WHERE item_id = p_item_id;

    INSERT INTO public.knowledge_base_chunks
      (kb_id, item_id, chunk_index, content, token_count, embedding, tenant_id, created_by)
    SELECT
      v_kb_id,
      p_item_id,
      COALESCE((c->>'chunk_index')::int, 0),
      c->>'content',
      COALESCE((c->>'token_count')::int, 0),
      (c->>'embedding')::extensions.vector,
      v_ctx.tenant_id,
      v_ctx.user_id
    FROM jsonb_array_elements(p_chunks) AS c;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN fn_response_success(
      jsonb_build_array(jsonb_build_object('item_id', p_item_id, 'chunks', v_count)),
      'Chunks saved'
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_save_kb_chunks', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
