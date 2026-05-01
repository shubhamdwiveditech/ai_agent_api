CREATE OR REPLACE FUNCTION public.fn_can_access_row(p_row anyelement, p_ctx t_request_context)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ac            jsonb;
  v_created_by    integer;
  v_row_tenant_id integer;
  v_scope         text;
  v_row_roles     integer[];
BEGIN

  -- ── Extract columns from row ─────────────────────────────────
  v_ac            := (p_row).access_control;
  v_created_by    := (p_row).created_by;
  v_row_tenant_id := (p_row).tenant_id;

  -- ── ADMIN: access own tenant rows + public rows ──────────────
  IF p_ctx.is_admin THEN
    RETURN (
      v_row_tenant_id IS NULL
      OR v_row_tenant_id = 0
      OR v_row_tenant_id = p_ctx.tenant_id
    );
  END IF;

  -- ── NULL or empty access_control = default PRIVATE ──────────
  IF v_ac IS NULL OR v_ac = '{}'::jsonb THEN
    RETURN v_created_by = p_ctx.user_id;
  END IF;

  -- ── Resolve scope, missing scope = private ───────────────────
  v_scope := COALESCE(v_ac->>'scope', 'private');

  -- ── PUBLIC: cross tenant, no tenant check needed ─────────────
  IF v_scope = 'public' THEN
    RETURN true;
  END IF;

  -- ── Tenant boundary: protected + private must match ──────────
  IF v_row_tenant_id IS DISTINCT FROM p_ctx.tenant_id THEN
    RETURN false;
  END IF;

  -- ── PROTECTED: roles intersection ────────────────────────────
  IF v_scope = 'protected' THEN
    v_row_roles := ARRAY(
      SELECT jsonb_array_elements_text(v_ac->'roles')::integer
    );
    -- protected with no roles defined = misconfigured, deny
    IF array_length(v_row_roles, 1) IS NULL THEN
      RETURN false;
    END IF;
    RETURN p_ctx.role_ids && v_row_roles;
  END IF;

  -- ── PRIVATE: owner only ───────────────────────────────────────
  IF v_scope = 'private' THEN
    RETURN v_created_by = p_ctx.user_id;
  END IF;

  -- ── Unrecognised scope = private ─────────────────────────────
  RETURN v_created_by = p_ctx.user_id;

END;
$function$
