CREATE OR REPLACE FUNCTION public.fn_get_request_context(p_caller_function text DEFAULT NULL::text)
 RETURNS TABLE(tenant_id integer, user_id integer, caller_id integer, allowed_schema text, role_ids integer[], is_admin boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_caller_id integer := NULL;
  v_tenant_id integer;
  v_user_id   integer;
  v_api_key   text;
  v_auth_uid  uuid;
  v_schema    text;
  v_role_ids  integer[];
  v_is_admin  boolean;
BEGIN

  -- ── Resolve identity ────────────────────────────────────────
  BEGIN
    v_api_key := current_setting('request.headers', true)::json->>'x-api-key';
  EXCEPTION
    WHEN OTHERS THEN v_api_key := NULL;
  END;

  IF v_api_key IS NOT NULL AND v_api_key != '' THEN

    SELECT p.tenant_id, p.id, t.access_control->>'schema'
    INTO v_tenant_id, v_user_id, v_schema
    FROM profiles p
    INNER JOIN tenants t ON p.tenant_id = t.id
    WHERE p.access_control->>'x-api-key'        = v_api_key
      AND p.is_active = true
      AND t.is_active = true;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Invalid or inactive API key'
        USING ERRCODE = '28000';
    END IF;

  ELSE

    v_auth_uid := auth.uid();

    IF v_auth_uid IS NULL THEN
      RAISE EXCEPTION 'No valid authentication found (neither JWT nor API key)'
        USING ERRCODE = '28000';
    END IF;

    SELECT p.tenant_id, p.id, t.access_control->>'schema'
    INTO v_tenant_id, v_user_id, v_schema
    FROM profiles p
    INNER JOIN tenants t ON p.tenant_id = t.id
    WHERE p.user_id  = v_auth_uid
      AND t.is_active = true
      AND p.is_active = true;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Authenticated user not found or inactive in profiles table'
        USING ERRCODE = '28000';
    END IF;

  END IF;

  -- ── Resolve roles and admin from profiles ONCE ──────────────
  SELECT
    ARRAY(
      SELECT jsonb_array_elements_text(p.access_control->'roles')::integer
      FROM profiles p
      WHERE p.id = v_user_id
    ),
    COALESCE(
      (
        SELECT (p.access_control->>'is_admin')::boolean
        FROM profiles p
        WHERE p.id = v_user_id
      ),
      false
    )
  INTO v_role_ids, v_is_admin;

  IF v_schema IS NULL THEN
    v_schema := 'public';
  END IF;

  RETURN QUERY
  SELECT
    v_tenant_id,
    v_user_id,
    v_caller_id,
    v_schema,
    v_role_ids,
    v_is_admin;

END;
$function$
