CREATE OR REPLACE FUNCTION public.fn_update_user_profile(p_id integer, p_user_name text DEFAULT NULL::text, p_role_ids integer[] DEFAULT NULL::integer[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_ctx     t_request_context;
  v_ac      jsonb;
  v_profile jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_update_user_profile');

    SELECT COALESCE(access_control, '{}'::jsonb) INTO v_ac
    FROM public.profiles
    WHERE id = p_id AND tenant_id = v_ctx.tenant_id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'User not found or access denied';
    END IF;

    IF p_role_ids IS NOT NULL THEN
      v_ac := v_ac || jsonb_build_object('roles', to_jsonb(p_role_ids));
    END IF;

    UPDATE public.profiles
       SET user_name      = COALESCE(NULLIF(trim(coalesce(p_user_name, '')), ''), user_name),
           access_control = v_ac,
           updated_at     = now(),
           updated_by     = v_ctx.user_id
     WHERE id = p_id
       AND tenant_id = v_ctx.tenant_id;

    SELECT to_jsonb(t) INTO v_profile
    FROM (
      SELECT id, user_id, email, user_name, is_active, access_control,
             created_at, updated_at
      FROM public.profiles WHERE id = p_id
    ) t;

    RETURN fn_response_success(jsonb_build_array(v_profile), 'User updated successfully');
  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_update_user_profile', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$
