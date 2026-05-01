CREATE OR REPLACE FUNCTION public.fn_search_kb_chunks(p_query_embedding vector, p_kb_ids integer[] DEFAULT NULL::integer[], p_match_threshold double precision DEFAULT 0.3, p_match_count integer DEFAULT 6)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'extensions'
AS $function$
DECLARE
  v_tenant_id integer;
  v_results jsonb;
BEGIN
  v_tenant_id := get_current_tenant_id();

  IF v_tenant_id IS NULL THEN
    RETURN jsonb_build_object(
      'is_success', false,
      'message', 'No tenant context'
    );
  END IF;

  WITH ranked AS (
    SELECT
      c.id            AS chunk_id,
      c.item_id,
      c.kb_id,
      c.chunk_index,
      c.content,
      i.name          AS item_name,
      i.item_type,
      i.url           AS item_url,
      kb.name         AS kb_name,
      1 - (c.embedding <=> p_query_embedding) AS similarity
    FROM public.knowledge_base_chunks c
    JOIN public.knowledge_base_items  i  ON i.id  = c.item_id
    JOIN public.knowledge_bases       kb ON kb.id = c.kb_id
    WHERE c.tenant_id = v_tenant_id
      AND c.embedding IS NOT NULL
      AND i.is_active = true
      AND kb.is_active = true
      AND (p_kb_ids IS NULL OR c.kb_id = ANY(p_kb_ids))
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT GREATEST(p_match_count, 1)
  )
  SELECT jsonb_agg(
           jsonb_build_object(
             'chunk_id',   chunk_id,
             'item_id',    item_id,
             'kb_id',      kb_id,
             'chunk_index',chunk_index,
             'content',    content,
             'item_name',  item_name,
             'item_type',  item_type,
             'item_url',   item_url,
             'kb_name',    kb_name,
             'similarity', similarity
           )
           ORDER BY similarity DESC
         )
  INTO v_results
  FROM ranked
  WHERE similarity >= p_match_threshold;

  RETURN jsonb_build_object(
    'is_success', true,
    'data', COALESCE(v_results, '[]'::jsonb)
  );
END;
$function$
