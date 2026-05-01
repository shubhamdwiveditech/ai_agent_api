CREATE OR REPLACE FUNCTION public.fn_save_global_variable(p_id integer DEFAULT NULL::integer, p_name text DEFAULT NULL::text, p_value text DEFAULT NULL::text, p_type text DEFAULT 'string'::text, p_description text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx  t_request_context;
  v_id   integer;
  v_row  jsonb;
  v_type text;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_global_variable');

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;
    IF p_value IS NULL THEN
      RAISE EXCEPTION 'Value is required';
    END IF;

    v_type := lower(coalesce(p_type, 'string'));
    IF v_type NOT IN ('string','boolean','integer','secret') THEN
      RAISE EXCEPTION 'Type must be one of: string, boolean, integer, secret';
    END IF;

    IF p_id IS NULL OR p_id = 0 THEN
      IF EXISTS (
        SELECT 1 FROM public.global_variables
        WHERE tenant_id = v_ctx.tenant_id
          AND COALESCE(is_active, true) = true
          AND lower(name) = lower(trim(p_name))
      ) THEN
        RAISE EXCEPTION 'A variable with this name already exists';
      END IF;

      INSERT INTO public.global_variables (name, value, description, type, tenant_id, is_active, created_by, created_at, updated_by, updated_at)
      VALUES (trim(p_name), p_value, NULLIF(trim(coalesce(p_description, '')), ''), v_type,
              v_ctx.tenant_id, true, v_ctx.user_id, now(), v_ctx.user_id, now())
      RETURNING id INTO v_id;
    ELSE
      IF NOT EXISTS (
        SELECT 1 FROM public.global_variables
        WHERE id = p_id AND tenant_id = v_ctx.tenant_id
      ) THEN
        RAISE EXCEPTION 'Variable not found or access denied';
      END IF;

      IF EXISTS (
        SELECT 1 FROM public.global_variables
        WHERE tenant_id = v_ctx.tenant_id
          AND id <> p_id
          AND COALESCE(is_active, true) = true
          AND lower(name) = lower(trim(p_name))
      ) THEN
        RAISE EXCEPTION 'A variable with this name already exists';
      END IF;

      UPDATE public.global_variables
         SET name        = trim(p_name),
             value       = p_value,
             description = NULLIF(trim(coalesce(p_description, '')), ''),
             type        = v_type,
             updated_at  = now(),
             updated_by  = v_ctx.user_id
       WHERE id = p_id
         AND tenant_id = v_ctx.tenant_id;

      v_id := p_id;
    END IF;

    SELECT to_jsonb(t) INTO v_row
    FROM (
      SELECT id, name, value, description, type,
             COALESCE(access_control, '{}'::jsonb) AS access_control,
             created_at, updated_at,
             '[]'::jsonb AS roles
      FROM public.global_variables WHERE id = v_id
    ) t;

    RETURN fn_response_success(
      jsonb_build_array(v_row),
      CASE WHEN p_id IS NULL OR p_id = 0 THEN 'Variable created successfully' ELSE 'Variable updated successfully' END
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_save_global_variable', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
