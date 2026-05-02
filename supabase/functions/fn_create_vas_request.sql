create or replace function public.fn_create_vas_request (
  p_service_type text default null,
  p_full_name text default null,
  p_email text default null,
  p_mobile_no text default null,
  p_service_detail text default null,
  p_remarks text default null
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
set
  search_path to 'public' as $function$
/*
====================================================
Copyright     : AI App, 2026
Created By    : Shubham Dwivedi
Modified Date : 02-May-2026
Description   : Create VAS service request
====================================================
SET LOCAL request.jwt.claim.sub = 'ca9f793b-2725-4fed-be19-21e17e429c4f';
select fn_create_vas_request('SMS' , 'Pratul Dwivedi', 'pratul@gmail.com', '9999999999', '','')
*/
DECLARE
  v_ctx  t_request_context;
  v_id   integer;
  v_row  jsonb;
BEGIN
  BEGIN
    v_ctx := fn_get_request_context('fn_create_vas_request');

    IF v_ctx.tenant_id IS NULL THEN
      RAISE EXCEPTION 'No tenant context';
    END IF;

    -- Validations
    IF p_service_type IS NULL OR length(trim(p_service_type)) = 0 THEN
      RAISE EXCEPTION 'Service type is required';
    END IF;

    IF p_email IS NULL OR length(trim(p_email)) = 0 THEN
      RAISE EXCEPTION 'Email is required';
    END IF;

    IF p_email !~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$' THEN
      RAISE EXCEPTION 'Invalid email address';
    END IF;

    INSERT INTO public.vas_requests (
        service_type, full_name, email, mobile_no,
        service_detail, remarks,
        tenant_id, created_by, created_at
      ) VALUES (
        trim(p_service_type), trim(p_full_name), trim(p_email), trim(p_mobile_no),
        p_service_detail, p_remarks,
        v_ctx.tenant_id, v_ctx.user_id, now()
      )
      RETURNING id INTO v_id;

    SELECT to_jsonb(t) INTO v_row
    FROM (
      SELECT
        id, service_type, full_name, email, mobile_no,
        service_detail, remarks
      FROM public.vas_requests WHERE id = v_id
    ) t;

    RETURN fn_response_success( jsonb_build_array(v_row),'VAS request created successfully'
    );

  EXCEPTION WHEN OTHERS THEN
    RETURN fn_response_error('fn_create_vas_request', SQLERRM, '[]'::jsonb, v_ctx.tenant_id, v_ctx.user_id);
  END;
END;
$function$