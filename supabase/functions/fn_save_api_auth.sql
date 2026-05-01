CREATE OR REPLACE FUNCTION public.fn_save_api_auth(p_id integer DEFAULT NULL::integer, p_name text DEFAULT NULL::text, p_description text DEFAULT NULL::text, p_auth_type text DEFAULT 'none'::text, p_username text DEFAULT NULL::text, p_password text DEFAULT NULL::text, p_auth_url text DEFAULT NULL::text, p_auth_method text DEFAULT 'POST'::text, p_auth_payload text DEFAULT NULL::text, p_token_field_path text DEFAULT 'token'::text, p_headers jsonb DEFAULT '{}'::jsonb, p_data jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
  v_id integer;
  v_row jsonb;
  v_auth_type text;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_api_auth');

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;

    v_auth_type := lower(coalesce(p_auth_type, 'none'));
    IF v_auth_type NOT IN ('none','basic','bearer','api_key','oauth2') THEN
      RAISE EXCEPTION 'Invalid auth_type';
    END IF;

    IF p_id IS NULL OR p_id = 0 THEN
      IF EXISTS (
        SELECT 1 FROM public.api_auths
        WHERE tenant_id = v_ctx.tenant_id
          AND COALESCE(is_active, true) = true
          AND lower(name) = lower(trim(p_name))
      ) THEN
        RAISE EXCEPTION 'A credential with this name already exists';
      END IF;

      INSERT INTO public.api_auths (
        name, description, auth_type, username, password,
        auth_url, auth_method, auth_payload, token_field_path,
        headers, data, tenant_id, is_active,
        created_by, created_at, updated_by, updated_at
      ) VALUES (
        trim(p_name), NULLIF(trim(coalesce(p_description, '')), ''), v_auth_type,
        NULLIF(p_username, ''), NULLIF(p_password, ''),
        NULLIF(p_auth_url, ''), COALESCE(p_auth_method, 'POST'),
        NULLIF(p_auth_payload, ''), COALESCE(NULLIF(p_token_field_path, ''), 'token'),
        COALESCE(p_headers, '{}'::jsonb), COALESCE(p_data, '{}'::jsonb),
        v_ctx.tenant_id, true,
        v_ctx.user_id, now(), v_ctx.user_id, now()
      ) RETURNING id INTO v_id;
    ELSE
      IF NOT EXISTS (SELECT 1 FROM public.api_auths WHERE id = p_id AND tenant_id = v_ctx.tenant_id) THEN
        RAISE EXCEPTION 'Credential not found or access denied';
      END IF;

      IF EXISTS (
        SELECT 1 FROM public.api_auths
        WHERE tenant_id = v_ctx.tenant_id
          AND id <> p_id
          AND COALESCE(is_active, true) = true
          AND lower(name) = lower(trim(p_name))
      ) THEN
        RAISE EXCEPTION 'A credential with this name already exists';
      END IF;

      UPDATE public.api_auths
        SET name = trim(p_name),
            description = NULLIF(trim(coalesce(p_description, '')), ''),
            auth_type = v_auth_type,
            username = NULLIF(p_username, ''),
            password = NULLIF(p_password, ''),
            auth_url = NULLIF(p_auth_url, ''),
            auth_method = COALESCE(p_auth_method, 'POST'),
            auth_payload = NULLIF(p_auth_payload, ''),
            token_field_path = COALESCE(NULLIF(p_token_field_path, ''), 'token'),
            headers = COALESCE(p_headers, '{}'::jsonb),
            data = COALESCE(p_data, '{}'::jsonb),
            updated_at = now(),
            updated_by = v_ctx.user_id
      WHERE id = p_id AND tenant_id = v_ctx.tenant_id;

      v_id := p_id;
    END IF;

    SELECT to_jsonb(t) INTO v_row
    FROM (
      SELECT id, name, description, auth_type, username, password,
             auth_url, auth_method, auth_payload, token_field_path,
             COALESCE(headers, '{}'::jsonb) AS headers,
             COALESCE(data, '{}'::jsonb) AS data,
             COALESCE(metadata, '{}'::jsonb) AS metadata,
             COALESCE(access_control, '{}'::jsonb) AS access_control,
             created_at, updated_at,
             '[]'::jsonb AS roles
      FROM public.api_auths WHERE id = v_id
    ) t;

    RETURN fn_response_success(
      jsonb_build_array(v_row),
      CASE WHEN p_id IS NULL OR p_id = 0 THEN 'Credential created successfully' ELSE 'Credential updated successfully' END
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_save_api_auth', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
