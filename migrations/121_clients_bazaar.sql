-- MIG-121 · Tabla canónica clientes Bazzar (tablet + web)
-- Nombre holding: clients-bazaar → public.clients_bazaar (sin guión en SQL)
-- Idempotente · seguro re-ejecutar

-- 1) Renombrar legacy cliente_web si existe
DO $$
BEGIN
  IF to_regclass('public.clients_bazaar') IS NULL
     AND to_regclass('public.cliente_web') IS NOT NULL THEN
    ALTER TABLE public.cliente_web RENAME TO clients_bazaar;
  END IF;
END $$;

-- 2) Crear tabla si no hay legacy
CREATE TABLE IF NOT EXISTS public.clients_bazaar (
  id              bigserial PRIMARY KEY,
  cedula          text NOT NULL,
  nombre          text NOT NULL DEFAULT '',
  apellido        text,
  email           text,
  telefono        text,
  direccion       text,
  canal_registro  text NOT NULL DEFAULT 'TIENDA'
    CHECK (canal_registro IN ('TIENDA', 'TABLET', 'WEB')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 3) Columnas que pueden faltar en tabla renombrada
ALTER TABLE public.clients_bazaar
  ADD COLUMN IF NOT EXISTS nombre         text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS apellido       text,
  ADD COLUMN IF NOT EXISTS email          text,
  ADD COLUMN IF NOT EXISTS telefono       text,
  ADD COLUMN IF NOT EXISTS direccion      text,
  ADD COLUMN IF NOT EXISTS canal_registro text NOT NULL DEFAULT 'TIENDA',
  ADD COLUMN IF NOT EXISTS created_at     timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at     timestamptz NOT NULL DEFAULT now();

-- 4) Unicidad cédula (clave de negocio Bazzar)
CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_bazaar_cedula
  ON public.clients_bazaar (cedula);

-- 5) Índice búsqueda teléfono (checkout / POS)
CREATE INDEX IF NOT EXISTS idx_clients_bazaar_telefono
  ON public.clients_bazaar (telefono)
  WHERE telefono IS NOT NULL AND telefono <> '';

-- 6) FK opcional en tickets POS (solo si existe la tabla)
DO $$
BEGIN
  IF to_regclass('public.ticket_venta_pos') IS NOT NULL THEN
    ALTER TABLE public.ticket_venta_pos
      ADD COLUMN IF NOT EXISTS clients_bazaar_id bigint
        REFERENCES public.clients_bazaar(id);
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.ticket_venta_pos') IS NOT NULL THEN
    CREATE INDEX IF NOT EXISTS idx_ticket_venta_pos_clients_bazaar
      ON public.ticket_venta_pos (clients_bazaar_id)
      WHERE clients_bazaar_id IS NOT NULL;
  END IF;
END $$;

COMMENT ON TABLE public.clients_bazaar IS
  'Clientes finales Bazzar — única verdad tablet + web. No mezclar con cliente_v2 (RIMEC).';
