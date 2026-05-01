CREATE OR REPLACE FUNCTION public.fn_list_kb_items(p_kb_id integer, p_search text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx    t_request_context;
  v_result jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_list_kb_items');

    IF NOT EXISTS (
      SELECT 1 FROM public.knowledge_bases
      WHERE id = p_kb_id AND tenant_id = v_ctx.tenant_id
    ) THEN
      RAISE EXCEPTION 'Knowledge base not found or access denied';
    END IF;

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'created_at') DESC), '[]'::jsonb)
    INTO v_result
    FROM (
      SELECT i.id, i.kb_id, i.name, i.item_type, i.file_type, i.file_size,
             i.storage_path, i.url, i.embed_status, i.is_embedded, i.embed_error,
             i.access_control,
             i.created_at, i.updated_at
      FROM public.knowledge_base_items i
      WHERE i.kb_id = p_kb_id
        AND COALESCE(i.is_active, true) = true
        AND (p_search IS NULL OR p_search = '' OR i.name ILIKE '%' || p_search || '%')
      ORDER BY i.created_at DESC
    ) t;

    RETURN fn_response_success(v_result, 'Items retrieved',
      200, COALESCE(jsonb_array_length(v_result), 0), COALESCE(jsonb_array_length(v_result), 0), 1);
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_list_kb_items', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
