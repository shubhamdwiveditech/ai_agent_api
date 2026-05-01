CREATE OR REPLACE FUNCTION public.fn_get_prompts()
 RETURNS TABLE(id integer, prompt text)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT p.id, p.prompt
  FROM public.prompts p
  WHERE p.is_active = true
    AND p.tenant_id = public.get_current_tenant_id()
  ORDER BY p.id ASC;
$function$
