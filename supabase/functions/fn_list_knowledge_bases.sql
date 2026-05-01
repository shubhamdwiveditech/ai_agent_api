CREATE OR REPLACE FUNCTION public.fn_list_knowledge_bases(p_search text DEFAULT NULL::text, p_limit integer DEFAULT 200)
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
    v_ctx := fn_get_request_context('fn_list_knowledge_bases');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'created_at') DESC), '[]'::jsonb)
    INTO v_result
    FROM (
      SELECT
        kb.id,
        kb.name,
        kb.description,
        kb.parent_id,
        kb.access_control,
        kb.created_at,
        kb.updated_at,
        COALESCE((
          SELECT count(*) FROM public.knowledge_base_items i
          WHERE i.kb_id = kb.id AND COALESCE(i.is_active, true) = true
        ), 0)::int AS item_count,
        COALESCE((
          SELECT count(*) FROM public.knowledge_bases c
          WHERE c.parent_id = kb.id
            AND c.tenant_id = v_ctx.tenant_id
            AND COALESCE(c.is_active, true) = true
        ), 0)::int AS child_count
      FROM public.knowledge_bases kb
      WHERE kb.tenant_id = v_ctx.tenant_id
        AND COALESCE(kb.is_active, true) = true
        AND (p_search IS NULL OR p_search = '' OR kb.name ILIKE '%' || p_search || '%')
      ORDER BY kb.created_at DESC
      LIMIT GREATEST(COALESCE(p_limit, 200), 1)
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Knowledge bases retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0),
      p_page_size     := COALESCE(p_limit, 200),
      p_page_index    := 1
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_list_knowledge_bases', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
