CREATE OR REPLACE FUNCTION public.fn_update_access_control(p_id integer, p_page_id integer DEFAULT NULL::integer, p_route_name text DEFAULT NULL::text, p_access_control jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx            t_request_context;
  v_id_column      text;
  v_sql            text;
  v_scope          text;
  v_roles          integer[];
  v_access_control jsonb;
  v_ac             jsonb;
  v_created_by     integer;
  v_raw_table   text;   -- raw metadata value, e.g. "profiles" or "tenants.profiles"
  v_schema_name text;   -- resolved schema
  v_table_name  text;   -- resolved bare table name
BEGIN

  -- ── Resolve full context ────────────────────────────────────────
  v_ctx := fn_get_request_context('fn_update_access_control');

  -- ── NULL / empty → safe private default ────────────────────────
  IF p_access_control IS NULL OR p_access_control = '{}'::jsonb THEN
    p_access_control := '{"scope":"private","roles":[]}'::jsonb;
  END IF;

  -- ── Scope validation ────────────────────────────────────────────
  v_scope := p_access_control->>'scope';

  IF v_scope IS NULL OR v_scope NOT IN ('private', 'protected', 'public') THEN
    RAISE EXCEPTION 'access_control: invalid scope "%"', COALESCE(v_scope, '<null>')
      USING ERRCODE = '22023';
  END IF;

  -- ── Roles validation ────────────────────────────────────────────
  IF p_access_control ? 'roles' THEN
    IF jsonb_typeof(p_access_control->'roles') <> 'array' THEN
      RAISE EXCEPTION 'access_control: "roles" must be a JSON array'
        USING ERRCODE = '22023';
    END IF;

    BEGIN
      v_roles := ARRAY(
        SELECT jsonb_array_elements_text(p_access_control->'roles')::integer
      );
    EXCEPTION WHEN invalid_text_representation THEN
      RAISE EXCEPTION 'access_control: "roles" must contain only integers'
        USING ERRCODE = '22023';
    END;
  ELSE
    v_roles := ARRAY[]::integer[];
  END IF;

  -- ── Semantic rules per scope ────────────────────────────────────
  CASE v_scope
    WHEN 'protected' THEN
      IF array_length(v_roles, 1) IS NULL THEN
        RAISE EXCEPTION 'access_control: protected scope requires at least one role'
          USING ERRCODE = '22023';
      END IF;

    WHEN 'private', 'public' THEN
      v_roles := ARRAY[]::integer[];   -- roles are meaningless, strip silently
  END CASE;

  -- ── Build canonical output (no extra keys pass through) ────────
  v_access_control := jsonb_build_object(
    'scope', v_scope,
    'roles', to_jsonb(v_roles)
  );

  -- ── Resolve table + PK column from pages config ─────────────────
  SELECT
    COALESCE(binding_id_name, 'id'),
    metadata->>'table_name'
  INTO
    v_id_column,
    v_raw_table
  FROM  public.pages
  WHERE is_active = true
    AND (
      (p_page_id    IS NOT NULL AND id         = p_page_id)
   OR (p_route_name IS NOT NULL AND route_name = p_route_name)
    )
  LIMIT 1;



  IF v_raw_table IS NULL THEN
    RAISE EXCEPTION
      'access_control: no active page found for page_id=% / route="%"',
      p_page_id, p_route_name
      USING ERRCODE = '42501';
  END IF;


  IF position('.' IN v_raw_table) > 0 THEN
    v_schema_name := split_part(v_raw_table, '.', 1);  -- "tenants"
    v_table_name  := split_part(v_raw_table, '.', 2);  -- "profiles"
  ELSE
    v_schema_name := 'public';   -- default fallback
    v_table_name  := v_raw_table;
  END IF;


  IF v_table_name IS NULL THEN
    RAISE EXCEPTION 'access_control: page config is missing metadata.table_name'
      USING ERRCODE = '42501';
  END IF;

  -- ── Fetch RBAC fields from the target row ───────────────────────
  --    FOR UPDATE serialises concurrent access_control changes.
   v_sql := format(
    'SELECT access_control, created_by, tenant_id
     FROM   %I.%I
     WHERE  %I = $1
     FOR    UPDATE',
    v_schema_name,
    v_table_name,
    v_id_column
  );

  EXECUTE v_sql
    INTO  v_ac, v_created_by
    USING p_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION
      'access_control: row % not found in table "%"',
      p_id, v_table_name
      USING ERRCODE = 'P0002';
  END IF;

  -- ── Authorization (runs after fetch so we have created_by) ──────
  IF NOT v_ctx.is_admin AND v_created_by IS DISTINCT FROM v_ctx.user_id THEN
    RAISE EXCEPTION 'access_control: permission denied (not owner)'
      USING ERRCODE = '42501';
  END IF;

  -- ── Merge: preserve all existing keys, overwrite only scope + roles
  --    Order matters: right-hand side wins on duplicate keys.
  --    Existing keys like "is_admin", "x-api-key" etc. are kept intact.
  v_access_control :=
    COALESCE(v_ac, '{}'::jsonb)               -- existing (base)
    ||                                         -- merge operator
    jsonb_build_object(                        -- only our two managed keys
      'scope', v_scope,
      'roles', to_jsonb(v_roles)
    );

  -- ── Write the sanitised value back ──────────────────────────────
 v_sql := format(
    'UPDATE %I.%I
     SET    access_control = $1,
            updated_at     = now()
     WHERE  %I = $2',
    v_schema_name,
    v_table_name,
    v_id_column
  );
  EXECUTE v_sql USING v_access_control, p_id;

  RETURN fn_response_success(
    p_data          := v_access_control,
    p_message       := 'Access control updated successfully',
    p_total_records := 1,
    p_page_size     := 1,
    p_page_index    := 1
  );

EXCEPTION WHEN OTHERS THEN
  RETURN fn_response_error(
    p_function_name := 'fn_update_access_control',
    p_message       := SQLERRM,
    p_data          := '[]'::jsonb,
    p_tenant_id     := v_ctx.tenant_id,
    p_user_id       := v_ctx.user_id
  );

END;
$function$
