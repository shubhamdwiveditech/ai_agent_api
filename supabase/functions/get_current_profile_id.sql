CREATE OR REPLACE FUNCTION public.get_current_profile_id()
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT id FROM public.profiles
  WHERE user_id = auth.uid()
    AND is_active = true
  LIMIT 1;
$function$
