CREATE OR REPLACE FUNCTION public.fn_resolve_variables(p_text text, p_vars jsonb)
 RETURNS text
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
/*
    Replaces every {{KEY}} in p_text with the matching
    value from p_vars. Unknown keys are left untouched.
*/
DECLARE
    v_key   TEXT;
    v_val   TEXT;
    v_out   TEXT := p_text;
BEGIN

    IF v_out IS NULL OR p_vars IS NULL THEN
        RETURN v_out;
    END IF;

    FOR v_key, v_val IN
        SELECT key, value #>> '{}'   -- unwrap jsonb scalar to text
        FROM jsonb_each(p_vars)
    LOOP

        v_out := replace(v_out, '{{' || v_key || '}}', v_val);

    END LOOP;

    RETURN v_out;

END;
$function$
