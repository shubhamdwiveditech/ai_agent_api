CREATE OR REPLACE FUNCTION public.fn_save_api_config(p_id integer DEFAULT NULL::integer, p_api_type text DEFAULT 'analytics'::text, p_name text DEFAULT NULL::text, p_url text DEFAULT NULL::text, p_method text DEFAULT 'GET'::text, p_headers jsonb DEFAULT '{}'::jsonb, p_body text DEFAULT NULL::text, p_fields jsonb DEFAULT '[]'::jsonb, p_api_auth_id integer DEFAULT NULL::integer, p_data_field_path text DEFAULT 'data'::text, p_data jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx t_request_context;
  v_id integer;
  v_row jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_save_api_config');

    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
      RAISE EXCEPTION 'Name is required';
    END IF;
    IF p_url IS NULL OR length(trim(p_url)) = 0 THEN
      RAISE EXCEPTION 'URL is required';
    END IF;

    IF p_id IS NULL OR p_id = 0 THEN
      IF EXISTS (
        SELECT 1 FROM public.api_config
        WHERE tenant_id = v_ctx.tenant_id
          AND COALESCE(is_active, true) = true
          AND lower(name) = lower(trim(p_name))
      ) THEN
        RAISE EXCEPTION 'An API config with this name already exists';
      END IF;

      INSERT INTO public.api_config (
        api_type, name, url, method, headers, body, fields,
        api_auth_id, data_field_path, data,
        tenant_id, is_active,
        created_by, created_at, updated_by, updated_at
      ) VALUES (
        COALESCE(NULLIF(p_api_type, ''), 'analytics'),
        trim(p_name), trim(p_url), COALESCE(p_method, 'GET'),
        COALESCE(p_headers, '{}'::jsonb), NULLIF(p_body, ''),
        COALESCE(p_fields, '[]'::jsonb),
        p_api_auth_id,
        COALESCE(NULLIF(p_data_field_path, ''), 'data'),
        COALESCE(p_data, '{}'::jsonb),
        v_ctx.tenant_id, true,
        v_ctx.user_id, now(), v_ctx.user_id, now()
      ) RETURNING id INTO v_id;
    ELSE
      IF NOT EXISTS (SELECT 1 FROM public.api_config WHERE id = p_id AND tenant_id = v_ctx.tenant_id) THEN
        RAISE EXCEPTION 'API config not found or access denied';
      END IF;

      IF EXISTS (
        SELECT 1 FROM public.api_config
        WHERE tenant_id = v_ctx.tenant_id
          AND id <> p_id
          AND COALESCE(is_active, true) = true
          AND lower(name) = lower(trim(p_name))
      ) THEN
        RAISE EXCEPTION 'An API config with this name already exists';
      END IF;

      UPDATE public.api_config
        SET api_type = COALESCE(NULLIF(p_api_type, ''), api_type),
            name = trim(p_name),
            url = trim(p_url),
            method = COALESCE(p_method, 'GET'),
            headers = COALESCE(p_headers, '{}'::jsonb),
            body = NULLIF(p_body, ''),
            fields = COALESCE(p_fields, '[]'::jsonb),
            api_auth_id = p_api_auth_id,
            data_field_path = COALESCE(NULLIF(p_data_field_path, ''), 'data'),
            data = COALESCE(p_data, '{}'::jsonb),
            updated_at = now(),
            updated_by = v_ctx.user_id
      WHERE id = p_id AND tenant_id = v_ctx.tenant_id;

      v_id := p_id;
    END IF;

    SELECT to_jsonb(t) INTO v_row
    FROM (
      SELECT c.id, c.api_type, c.name, c.url, c.method,
             COALESCE(c.headers, '{}'::jsonb) AS headers,
             c.body,
             COALESCE(c.fields, '[]'::jsonb) AS fields,
             c.api_auth_id, c.data_field_path,
             COALESCE(c.data, '{}'::jsonb) AS data,
             COALESCE(c.metadata, '{}'::jsonb) AS metadata,
             COALESCE(c.access_control, '{}'::jsonb) AS access_control,
             c.created_at, c.updated_at,
             (SELECT a.name FROM public.api_auths a WHERE a.id = c.api_auth_id) AS api_auth_name,
             (SELECT a.auth_type FROM public.api_auths a WHERE a.id = c.api_auth_id) AS api_auth_type,
             '[]'::jsonb AS roles
      FROM public.api_config c WHERE c.id = v_id
    ) t;

    RETURN fn_response_success(
      jsonb_build_array(v_row),
      CASE WHEN p_id IS NULL OR p_id = 0 THEN 'API config created successfully' ELSE 'API config updated successfully' END
    );
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_save_api_config', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
