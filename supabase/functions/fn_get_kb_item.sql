create or replace function public.fn_get_kb_item (p_id integer default null::integer) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
set
  search_path to 'public' as $function$
DECLARE
  v_ctx    t_request_context;
  v_result jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_get_kb_item');

    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY (to_jsonb(t)->>'id')::int DESC), '[]'::jsonb)
    INTO   v_result
    FROM (
      SELECT i.*
      FROM   public.knowledge_base_items i
      WHERE i.id= p_id 
        AND  i.tenant_id = v_ctx.tenant_id
        AND  COALESCE(i.is_active, true) = true
    ) t;

    RETURN fn_response_success(
      p_data          := v_result,
      p_message       := 'Roles retrieved',
      p_total_records := COALESCE(jsonb_array_length(v_result), 0)
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_get_kb_item', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$