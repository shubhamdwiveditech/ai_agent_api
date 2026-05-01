CREATE OR REPLACE FUNCTION public.fn_create_knowledge_base(p_name text, p_description text DEFAULT NULL::text, p_parent_id integer DEFAULT NULL::integer)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
  v_id  integer;
  v_kb  jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_create_knowledge_base');

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;

    -- Validate parent belongs to same tenant
    IF p_parent_id IS NOT NULL THEN
      IF NOT EXISTS (
        SELECT 1 FROM public.knowledge_bases
        WHERE id = p_parent_id
          AND tenant_id = v_ctx.tenant_id
          AND COALESCE(is_active, true) = true
      ) THEN
        RAISE EXCEPTION 'Parent knowledge base not found or access denied';
      END IF;
    END IF;

    INSERT INTO public.knowledge_bases (name, description, parent_id, tenant_id, created_by, updated_by, is_active)
    VALUES (trim(p_name), NULLIF(trim(coalesce(p_description, '')), ''), p_parent_id,
            v_ctx.tenant_id, v_ctx.user_id, v_ctx.user_id, true)
    RETURNING id INTO v_id;

    SELECT to_jsonb(t) INTO v_kb
    FROM (
      SELECT id, name, description, parent_id, created_at, updated_at,
             0::int AS item_count, 0::int AS child_count
      FROM public.knowledge_bases WHERE id = v_id
    ) t;

    RETURN fn_response_success(jsonb_build_array(v_kb), 'Knowledge base created', 200, 1, 1, 1);
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_create_knowledge_base', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
