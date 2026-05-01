CREATE OR REPLACE FUNCTION public.fn_delete_knowledge_base(p_id integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
  v_ids integer[];
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_delete_knowledge_base');

    IF NOT EXISTS (
      SELECT 1 FROM public.knowledge_bases
      WHERE id = p_id AND tenant_id = v_ctx.tenant_id
    ) THEN
      RAISE EXCEPTION 'Knowledge base not found or access denied';
    END IF;

    -- Collect this KB and all descendants (tenant-scoped)
    WITH RECURSIVE tree AS (
      SELECT id FROM public.knowledge_bases
      WHERE id = p_id AND tenant_id = v_ctx.tenant_id
      UNION ALL
      SELECT kb.id FROM public.knowledge_bases kb
      INNER JOIN tree t ON kb.parent_id = t.id
      WHERE kb.tenant_id = v_ctx.tenant_id
    )
    SELECT array_agg(id) INTO v_ids FROM tree;

    IF v_ids IS NULL OR array_length(v_ids, 1) = 0 THEN
      RAISE EXCEPTION 'Knowledge base not found or access denied';
    END IF;

    DELETE FROM public.knowledge_base_chunks WHERE kb_id = ANY(v_ids);
    DELETE FROM public.knowledge_base_items  WHERE kb_id = ANY(v_ids);
    DELETE FROM public.knowledge_bases       WHERE id    = ANY(v_ids);

    RETURN fn_response_success('[]'::jsonb, 'Knowledge base deleted');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_delete_knowledge_base', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
