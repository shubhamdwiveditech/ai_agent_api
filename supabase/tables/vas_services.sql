create table public.vas_services (
  id serial not null,
  name text not null,
  service_type text null,
  description text null default 'none'::text,
  data jsonb null default '{}'::jsonb,
  metadata jsonb null default '{}'::jsonb,
  access_control jsonb null default '{}'::jsonb,
  tenant_id integer null,
  is_active boolean not null default true,
  created_by integer null,
  created_at timestamp without time zone not null default now(),
  updated_by integer null,
  updated_at timestamp without time zone not null default now(),
  constraint vas_services_pkey primary key (id)
) TABLESPACE pg_default;