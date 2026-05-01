CREATE OR REPLACE FUNCTION public.fn_get_profile()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
/*
============================================================================================
Copyright     : BLS, 2026
Created By    : Shubham Dwivedi
Modified Date : 26-Apr-2026
Description   : Get user profile after successful login
Example       :
                SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
                SELECT fn_get_profile();
============================================================================================
*/
DECLARE
    v_ctx       t_request_context;
    v_result    jsonb;
BEGIN
    BEGIN
        -- ── Resolve full context in one call ─────────────────
        v_ctx := fn_get_request_context('fn_get_profile');

        -- ── Fetch profile with tenant info ────────────────────
        SELECT jsonb_agg(to_jsonb(t))
        INTO   v_result
        FROM (
            SELECT
                p.id,
                p.user_id,
                p.tenant_id,
                p.email,
                p.user_name,
                p.data || jsonb_build_object('is_admin', (p.access_control->>'is_admin')::boolean) AS data,
                jsonb_build_object(
                    'id',       t.id,
                    'code',     t.code,
                    'data',     t.data,
                    'name',     t.name,
                    'domain',   t.domain,
                    'metadata', t.metadata
                ) AS tenant
            FROM  public.profiles p
            INNER JOIN public.tenants t ON t.id = p.tenant_id
            WHERE p.id        = v_ctx.user_id
              AND p.tenant_id = v_ctx.tenant_id 
              AND p.is_active = true
        ) t;

        -- ── Guard: profile not found or inactive ──────────────
        IF v_result IS NULL THEN
            RAISE EXCEPTION 'Profile not found or inactive';
        END IF;

        -- ── Return success ────────────────────────────────────
        RETURN fn_response_success(
            p_data          := v_result,
            p_message       := 'Profile retrieved successfully',
            p_total_records := 1,
            p_page_size     := 1,
            p_page_index    := 1
        );

    EXCEPTION WHEN OTHERS THEN
        -- ── Return error response ─────────────────────────────
        RETURN fn_response_error(
            p_function_name := 'fn_get_profile',
            p_message       := SQLERRM,
            p_data          := '[]'::jsonb,
            p_tenant_id     := v_ctx.tenant_id, 
            p_user_id       := v_ctx.user_id 
        );
    END;
END;
$function$
