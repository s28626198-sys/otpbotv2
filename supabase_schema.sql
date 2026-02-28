create table if not exists public.users (
  user_id bigint primary key,
  chat_id bigint,
  username text,
  full_name text,
  lang text not null default 'en',
  role text not null default 'pending',
  approval_notified boolean not null default false,
  approved_by bigint,
  approved_at bigint,
  balance numeric(18,6) not null default 0,
  activation_id text,
  activation_started_at bigint,
  service_code text,
  country_code text,
  provider_id text,
  phone text,
  polling integer not null default 0,
  created bigint not null default extract(epoch from now())::bigint,
  updated bigint not null default extract(epoch from now())::bigint
);

create table if not exists public.activations (
  activation_id text primary key,
  user_id bigint not null,
  chat_id bigint not null,
  service_code text,
  country_code text,
  provider_id text,
  phone text,
  status text not null default 'active',
  otp_code text,
  base_price numeric(18,6) not null default 0,
  charged_price numeric(18,6) not null default 0,
  refunded boolean not null default false,
  refund_amount numeric(18,6) not null default 0,
  created_at bigint not null default extract(epoch from now())::bigint,
  updated_at bigint not null default extract(epoch from now())::bigint
);

create table if not exists public.deposits (
  id bigserial primary key,
  user_id bigint not null,
  amount numeric(18,6) not null,
  txid text,
  screenshot_file_id text,
  status text not null default 'awaiting_proof',
  reviewed_by bigint,
  reviewed_at bigint,
  note text,
  created_at bigint not null default extract(epoch from now())::bigint,
  updated_at bigint not null default extract(epoch from now())::bigint
);

create table if not exists public.settings (
  key text primary key,
  value text not null,
  updated bigint not null default extract(epoch from now())::bigint
);

create index if not exists idx_users_role on public.users(role);
create index if not exists idx_activations_user_status on public.activations(user_id, status);
create index if not exists idx_deposits_status on public.deposits(status);

alter table public.users disable row level security;
alter table public.activations disable row level security;
alter table public.deposits disable row level security;
alter table public.settings disable row level security;
