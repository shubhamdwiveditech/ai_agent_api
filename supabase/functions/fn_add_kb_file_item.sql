CREATE OR REPLACE FUNCTION public.fn_add_kb_file_item(p_kb_id integer, p_name text, p_file_type text, p_file_size integer, p_storage_path text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx  t_request_context;
  v_id   integer;
  v_item jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_add_kb_file_item');

    IF NOT EXISTS (
      SELECT 1 FROM public.knowledge_bases
      WHERE id = p_kb_id AND tenant_id = v_ctx.tenant_id
    ) THEN
      RAISE EXCEPTION 'Knowledge base not found or access denied';
    END IF;

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;

    INSERT INTO public.knowledge_base_items (
      kb_id, name, item_type, file_type, file_size, storage_path,
      tenant_id, created_by, updated_by, is_active,
      embed_status, is_embedded
    )
    VALUES (
      p_kb_id, trim(p_name), 'file', p_file_type, COALESCE(p_file_size, 0), p_storage_path,
      v_ctx.tenant_id, v_ctx.user_id, v_ctx.user_id, true,
      'pending', false
    )
    RETURNING id INTO v_id;

    SELECT to_jsonb(t) INTO v_item FROM (
      SELECT id, kb_id, name, item_type, file_type, file_size, storage_path,
             url, embed_status, is_embedded, embed_error, created_at, updated_at
      FROM public.knowledge_base_items WHERE id = v_id
    ) t;

    RETURN fn_response_success(jsonb_build_array(v_item), 'File added');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_add_kb_file_item', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
