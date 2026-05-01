CREATE OR REPLACE FUNCTION public.fn_update_knowledge_base(p_id integer, p_name text, p_description text DEFAULT NULL::text, p_parent_id integer DEFAULT NULL::integer, p_update_parent boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx     t_request_context;
  v_kb      jsonb;
  v_cursor  integer;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_update_knowledge_base');

    IF NOT EXISTS (
      SELECT 1 FROM public.knowledge_bases
      WHERE id = p_id AND tenant_id = v_ctx.tenant_id
    ) THEN
      RAISE EXCEPTION 'Knowledge base not found or access denied';
    END IF;

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;

    -- If parent change is requested, validate
    IF p_update_parent THEN
      IF p_parent_id IS NOT NULL THEN
        IF p_parent_id = p_id THEN
          RAISE EXCEPTION 'A knowledge base cannot be its own parent';
        END IF;

        IF NOT EXISTS (
          SELECT 1 FROM public.knowledge_bases
          WHERE id = p_parent_id
            AND tenant_id = v_ctx.tenant_id
            AND COALESCE(is_active, true) = true
        ) THEN
          RAISE EXCEPTION 'Parent knowledge base not found or access denied';
        END IF;

        -- Cycle check: walk up the proposed parent's ancestors;
        -- if we encounter p_id, it would create a cycle.
        v_cursor := p_parent_id;
        WHILE v_cursor IS NOT NULL LOOP
          IF v_cursor = p_id THEN
            RAISE EXCEPTION 'Cannot move a knowledge base under one of its descendants';
          END IF;
          SELECT parent_id INTO v_cursor
          FROM public.knowledge_bases
          WHERE id = v_cursor;
        END LOOP;
      END IF;

      UPDATE public.knowledge_bases
         SET name        = trim(p_name),
             description = NULLIF(trim(coalesce(p_description, '')), ''),
             parent_id   = p_parent_id,
             updated_at  = now(),
             updated_by  = v_ctx.user_id
       WHERE id = p_id;
    ELSE
      UPDATE public.knowledge_bases
         SET name        = trim(p_name),
             description = NULLIF(trim(coalesce(p_description, '')), ''),
             updated_at  = now(),
             updated_by  = v_ctx.user_id
       WHERE id = p_id;
    END IF;

    SELECT to_jsonb(t) INTO v_kb
    FROM (
      SELECT kb.id, kb.name, kb.description, kb.parent_id, kb.created_at, kb.updated_at,
             COALESCE((SELECT count(*) FROM public.knowledge_base_items i
                        WHERE i.kb_id = kb.id AND COALESCE(i.is_active, true) = true), 0)::int AS item_count,
             COALESCE((SELECT count(*) FROM public.knowledge_bases c
                        WHERE c.parent_id = kb.id
                          AND c.tenant_id = v_ctx.tenant_id
                          AND COALESCE(c.is_active, true) = true), 0)::int AS child_count
      FROM public.knowledge_bases kb WHERE kb.id = p_id
    ) t;

    RETURN fn_response_success(jsonb_build_array(v_kb), 'Knowledge base updated');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_update_knowledge_base', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
