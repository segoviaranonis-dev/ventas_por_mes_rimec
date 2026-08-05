-- MIG-122 · clients_bazaar · origen sellado vía tabla entes
-- entes.codigo: 1=RIMEC · 2=Fernando · 3=San Martín · 4=Palma · 5=Bazzar Web
-- Tablet: tienda_cliente_id 2100|2900|2400|2700|3100|3200

CREATE TABLE IF NOT EXISTS public.entes (
  id_ente    SERIAL PRIMARY KEY,
  codigo     INTEGER UNIQUE NOT NULL,
  nombre     TEXT NOT NULL,
  tipo       TEXT NOT NULL CHECK (tipo IN ('empresa', 'tienda')),
  activo     BOOLEAN DEFAULT true NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

INSERT INTO public.entes (codigo, nombre, tipo) VALUES
  (1, 'RIMEC', 'empresa'),
  (2, 'Fernando', 'tienda'),
  (3, 'San Martín', 'tienda'),
  (4, 'Palma', 'tienda'),
  (5, 'Bazzar Web', 'empresa')
ON CONFLICT (codigo) DO NOTHING;

ALTER TABLE public.clients_bazaar
  ADD COLUMN IF NOT EXISTS registro_ente_codigo INTEGER,
  ADD COLUMN IF NOT EXISTS registro_tienda_cliente_id INTEGER,
  ADD COLUMN IF NOT EXISTS ultimo_ente_codigo INTEGER,
  ADD COLUMN IF NOT EXISTS ultimo_tienda_cliente_id INTEGER;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_clients_bazaar_registro_ente'
  ) THEN
    ALTER TABLE public.clients_bazaar
      ADD CONSTRAINT fk_clients_bazaar_registro_ente
        FOREIGN KEY (registro_ente_codigo) REFERENCES public.entes(codigo);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_clients_bazaar_ultimo_ente'
  ) THEN
    ALTER TABLE public.clients_bazaar
      ADD CONSTRAINT fk_clients_bazaar_ultimo_ente
        FOREIGN KEY (ultimo_ente_codigo) REFERENCES public.entes(codigo);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_clients_bazaar_ente_bazzar'
  ) THEN
    ALTER TABLE public.clients_bazaar
      ADD CONSTRAINT chk_clients_bazaar_ente_bazzar
        CHECK (
          (registro_ente_codigo IS NULL OR registro_ente_codigo IN (2, 3, 4, 5))
          AND (ultimo_ente_codigo IS NULL OR ultimo_ente_codigo IN (2, 3, 4, 5))
        );
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_clients_bazaar_registro_ente
  ON public.clients_bazaar (registro_ente_codigo, registro_tienda_cliente_id);

CREATE INDEX IF NOT EXISTS idx_clients_bazaar_ultimo_ente
  ON public.clients_bazaar (ultimo_ente_codigo, ultimo_tienda_cliente_id);

COMMENT ON COLUMN public.clients_bazaar.registro_ente_codigo IS
  'FK entes.codigo — primer registro (2 Fernando · 3 San Martín · 4 Palma · 5 Web). No RIMEC(1).';
COMMENT ON COLUMN public.clients_bazaar.registro_tienda_cliente_id IS
  'Tablet: 2100|2900|2400|2700|3100|3200. Web Bazzar: 5000 (cliente_v2 canal e-commerce).';
COMMENT ON COLUMN public.clients_bazaar.ultimo_ente_codigo IS
  'Último contacto / alta — entes.codigo';
COMMENT ON COLUMN public.clients_bazaar.ultimo_tienda_cliente_id IS
  'Última tienda física tablet; NULL si web.';

-- Backfill legacy canal_registro
UPDATE public.clients_bazaar
SET
  registro_ente_codigo = 5,
  ultimo_ente_codigo = 5,
  registro_tienda_cliente_id = NULL,
  ultimo_tienda_cliente_id = NULL
WHERE canal_registro = 'WEB'
  AND registro_ente_codigo IS NULL;
