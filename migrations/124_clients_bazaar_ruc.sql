-- MIG-124 · clients_bazaar — RUC + razón social (registro POS/web)
ALTER TABLE public.clients_bazaar
  ADD COLUMN IF NOT EXISTS ruc text,
  ADD COLUMN IF NOT EXISTS razon_social text;

CREATE INDEX IF NOT EXISTS idx_clients_bazaar_ruc
  ON public.clients_bazaar (ruc)
  WHERE ruc IS NOT NULL AND btrim(ruc) <> '';

COMMENT ON COLUMN public.clients_bazaar.ruc IS 'RUC Paraguay — captura en alta cliente (POS/web).';
COMMENT ON COLUMN public.clients_bazaar.razon_social IS 'Razón social o unipersonal — alta cliente.';
