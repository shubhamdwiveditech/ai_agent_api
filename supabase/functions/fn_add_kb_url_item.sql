CREATE OR REPLACE FUNCTION public.fn_add_kb_url_item(p_kb_id integer, p_name text, p_url text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx  t_request_context;
  v_id   integer;
  v_item jsonb;
  v_name text;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_add_kb_url_item');

    IF NOT EXISTS (
      SELECT 1 FROM public.knowledge_bases
      WHERE id = p_kb_id AND tenant_id = v_ctx.tenant_id
    ) THEN
      RAISE EXCEPTION 'Knowledge base not found or access denied';
    END IF;

    IF p_url IS NULL OR length(trim(p_url)) = 0 THEN
      RAISE EXCEPTION 'URL is required';
    END IF;

    v_name := COALESCE(NULLIF(trim(coalesce(p_name, '')), ''), trim(p_url));

    INSERT INTO public.knowledge_base_items (
      kb_id, name, item_type, url,
      tenant_id, created_by, updated_by, is_active,
      embed_status, is_embedded
    )
    VALUES (
      p_kb_id, v_name, 'website', trim(p_url),
      v_ctx.tenant_id, v_ctx.user_id, v_ctx.user_id, true,
      'pending', false
    )
    RETURNING id INTO v_id;

    SELECT to_jsonb(t) INTO v_item FROM (
      SELECT id, kb_id, name, item_type, file_type, file_size, storage_path,
             url, embed_status, is_embedded, embed_error, created_at, updated_at
      FROM public.knowledge_base_items WHERE id = v_id
    ) t;

    RETURN fn_response_success(jsonb_build_array(v_item), 'Website added');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_add_kb_url_item', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
