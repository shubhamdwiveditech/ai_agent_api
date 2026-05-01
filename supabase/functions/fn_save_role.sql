CREATE OR REPLACE FUNCTION public.fn_save_role(p_id integer DEFAULT NULL::integer, p_name text DEFAULT NULL::text, p_descr text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx  t_request_context;
  v_id   integer;
  v_role jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_role');

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;

    IF p_id IS NULL OR p_id = 0 THEN
      INSERT INTO public.roles (name, descr, tenant_id, is_active, created_by, created_at, updated_by, updated_at)
      VALUES (trim(p_name), NULLIF(trim(coalesce(p_descr, '')), ''),
              v_ctx.tenant_id, true, v_ctx.user_id, now(), v_ctx.user_id, now())
      RETURNING id INTO v_id;
    ELSE
      IF NOT EXISTS (
        SELECT 1 FROM public.roles
        WHERE id = p_id AND tenant_id = v_ctx.tenant_id
      ) THEN
        RAISE EXCEPTION 'Role not found or access denied';
      END IF;

      UPDATE public.roles
         SET name       = trim(p_name),
             descr      = NULLIF(trim(coalesce(p_descr, '')), ''),
             updated_at = now(),
             updated_by = v_ctx.user_id
       WHERE id = p_id
         AND tenant_id = v_ctx.tenant_id;

      v_id := p_id;
    END IF;

    SELECT to_jsonb(t) INTO v_role
    FROM (
      SELECT id, name, descr, access_control, created_at, updated_at
      FROM public.roles WHERE id = v_id
    ) t;

    RETURN fn_response_success(
      jsonb_build_array(v_role),
      CASE WHEN p_id IS NULL OR p_id = 0 THEN 'Role created successfully' ELSE 'Role updated successfully' END
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_save_role', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
