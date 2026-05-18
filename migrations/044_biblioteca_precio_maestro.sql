-- ═══════════════════════════════════════════════════════════════════════════
-- 044 — Maestro Biblioteca de Casos (contenedor + exclusividad de líneas)
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS public.biblioteca_precio (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    proveedor_id    bigint      NOT NULL,
    nombre          text        NOT NULL,
    descripcion     text        NULL,
    activo          boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT biblioteca_precio_proveedor_nombre_uq UNIQUE (proveedor_id, nombre)
);

CREATE INDEX IF NOT EXISTS idx_biblioteca_precio_proveedor
    ON public.biblioteca_precio (proveedor_id) WHERE activo = true;

ALTER TABLE public.caso_precio_biblioteca
    ADD COLUMN IF NOT EXISTS biblioteca_id bigint NULL
        REFERENCES public.biblioteca_precio(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_cpb_biblioteca
    ON public.caso_precio_biblioteca (biblioteca_id) WHERE biblioteca_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.biblioteca_caso_linea (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    biblioteca_id       bigint NOT NULL REFERENCES public.biblioteca_precio(id) ON DELETE CASCADE,
    caso_biblioteca_id  bigint NOT NULL REFERENCES public.caso_precio_biblioteca(id) ON DELETE CASCADE,
    linea_id            bigint NOT NULL REFERENCES public.linea(id) ON DELETE CASCADE,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT biblioteca_caso_linea_bib_linea_uq UNIQUE (biblioteca_id, linea_id)
);

CREATE INDEX IF NOT EXISTS idx_bcl_caso
    ON public.biblioteca_caso_linea (caso_biblioteca_id);

ALTER TABLE public.precio_evento
    ADD COLUMN IF NOT EXISTS biblioteca_precio_id bigint NULL
        REFERENCES public.biblioteca_precio(id) ON DELETE SET NULL;

COMMENT ON TABLE public.biblioteca_precio IS
  'Maestro: contenedor de casos comerciales reutilizables por proveedor.';
COMMENT ON TABLE public.biblioteca_caso_linea IS
  'Exclusividad: una línea solo en un caso dentro de la misma biblioteca.';

COMMIT;

SELECT '044 aplicada: maestro biblioteca_precio' AS estado;
