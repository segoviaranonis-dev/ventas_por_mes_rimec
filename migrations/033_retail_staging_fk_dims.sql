-- =============================================================================
-- 033 · retail_multitienda_staging: FKs a maestros (Excel sin columnas extra)
-- Ejecutar después de 030 (y 031 si usás RLS). Si corriste 032, esta migración
-- quita las columnas texto y agrega *_id resueltos en app desde pilares.
-- Si falla al crear FKs por filas huérfanas: vaciá staging o reimportá lotes
-- con material_id/color_id coherentes antes de reintentar.
-- material_id / color_id en Excel siguen siendo códigos proveedor → se guardan
-- como material.id / color.id. Fallback semántico: filas RETAIL_OTROS (-999001).
-- =============================================================================

ALTER TABLE public.retail_multitienda_staging DROP COLUMN IF EXISTS marca;
ALTER TABLE public.retail_multitienda_staging DROP COLUMN IF EXISTS genero;
ALTER TABLE public.retail_multitienda_staging DROP COLUMN IF EXISTS estilo;
ALTER TABLE public.retail_multitienda_staging DROP COLUMN IF EXISTS tipo_1;

ALTER TABLE public.retail_multitienda_staging
    ADD COLUMN IF NOT EXISTS marca_id          bigint NULL,
    ADD COLUMN IF NOT EXISTS genero_id         bigint NULL,
    ADD COLUMN IF NOT EXISTS grupo_estilo_id   bigint NULL,
    ADD COLUMN IF NOT EXISTS tipo_1_id        bigint NULL;

COMMENT ON COLUMN public.retail_multitienda_staging.marca_id IS
  'FK marca_v2 — desde catálogo linea+ref; default fila sentinela descp_marca «Otros (retail staging)».';
COMMENT ON COLUMN public.retail_multitienda_staging.genero_id IS
  'FK genero — desde linea; default Otros.';
COMMENT ON COLUMN public.retail_multitienda_staging.grupo_estilo_id IS
  'FK grupo_estilo_v2 — desde linea_referencia/linea; default Otros.';
COMMENT ON COLUMN public.retail_multitienda_staging.tipo_1_id IS
  'FK tipo_1 — desde linea_referencia; default Otros.';
COMMENT ON COLUMN public.retail_multitienda_staging.material_id IS
  'FK public.material(id); Excel = codigo_proveedor resuelto en app.';
COMMENT ON COLUMN public.retail_multitienda_staging.color_id IS
  'FK public.color(id); Excel = codigo_proveedor resuelto en app.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_retail_staging_marca'
    ) THEN
        ALTER TABLE public.retail_multitienda_staging
            ADD CONSTRAINT fk_retail_staging_marca
            FOREIGN KEY (marca_id) REFERENCES public.marca_v2(id_marca);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_retail_staging_genero'
    ) THEN
        ALTER TABLE public.retail_multitienda_staging
            ADD CONSTRAINT fk_retail_staging_genero
            FOREIGN KEY (genero_id) REFERENCES public.genero(id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_retail_staging_grupo_estilo'
    ) THEN
        ALTER TABLE public.retail_multitienda_staging
            ADD CONSTRAINT fk_retail_staging_grupo_estilo
            FOREIGN KEY (grupo_estilo_id) REFERENCES public.grupo_estilo_v2(id_grupo_estilo);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_retail_staging_tipo_1'
    ) THEN
        ALTER TABLE public.retail_multitienda_staging
            ADD CONSTRAINT fk_retail_staging_tipo_1
            FOREIGN KEY (tipo_1_id) REFERENCES public.tipo_1(id_tipo_1);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_retail_staging_material'
    ) THEN
        ALTER TABLE public.retail_multitienda_staging
            ADD CONSTRAINT fk_retail_staging_material
            FOREIGN KEY (material_id) REFERENCES public.material(id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_retail_staging_color'
    ) THEN
        ALTER TABLE public.retail_multitienda_staging
            ADD CONSTRAINT fk_retail_staging_color
            FOREIGN KEY (color_id) REFERENCES public.color(id);
    END IF;
END $$;

-- Marca / género / material / color «Otros» para FKs de staging (idempotente).
-- Inserciones con PK explícita (MAX+1). Tablas con columna `id` como
-- GENERATED ALWAYS AS IDENTITY requieren OVERRIDING SYSTEM VALUE (genero, material, color).
-- marca_v2 usa id_marca: si también es ALWAYS, agregar OVERRIDING en ese INSERT.

-- ── marca_v2 (solo descp_marca; sin columna codigo) ──────────────────────────
INSERT INTO public.marca_v2 (id_marca, descp_marca)
SELECT s.new_id, 'Otros (retail staging)'
FROM (SELECT COALESCE(MAX(m.id_marca), 0) + 1 AS new_id FROM public.marca_v2 m) s
WHERE NOT EXISTS (
    SELECT 1 FROM public.marca_v2 mv
    WHERE lower(btrim(COALESCE(mv.descp_marca::text, '')))
        = lower(btrim('Otros (retail staging)'))
);

DO $$
DECLARE
    seqname text;
    mx      bigint;
BEGIN
    seqname := pg_get_serial_sequence('public.marca_v2', 'id_marca');
    IF seqname IS NOT NULL THEN
        SELECT COALESCE(MAX(id_marca), 0) INTO mx FROM public.marca_v2;
        PERFORM setval(seqname::regclass, mx, true);
    END IF;
END $$;

-- ── genero ───────────────────────────────────────────────────────────────────
INSERT INTO public.genero (id, codigo, descripcion, activo) OVERRIDING SYSTEM VALUE
SELECT s.new_id, 'RETAIL_OTROS', 'Otros (retail staging)', true
FROM (SELECT COALESCE(MAX(g.id), 0) + 1 AS new_id FROM public.genero g) s
WHERE NOT EXISTS (SELECT 1 FROM public.genero WHERE codigo = 'RETAIL_OTROS');

DO $$
DECLARE
    seqname text;
    mx      bigint;
BEGIN
    seqname := pg_get_serial_sequence('public.genero', 'id');
    IF seqname IS NOT NULL THEN
        SELECT COALESCE(MAX(id), 0) INTO mx FROM public.genero;
        PERFORM setval(seqname::regclass, mx, true);
    END IF;
END $$;

-- ── material sentinel (codigo_proveedor = -999001) por proveedor ───────────
INSERT INTO public.material (id, proveedor_id, codigo_proveedor, descripcion) OVERRIDING SYSTEM VALUE
SELECT b.base + row_number() OVER (ORDER BY p.id),
       p.id,
       -999001::bigint,
       'RETAIL_OTROS (staging)'
FROM public.proveedor_importacion p
CROSS JOIN LATERAL (
    SELECT COALESCE(MAX(m.id), 0) AS base FROM public.material m
) b
WHERE NOT EXISTS (
    SELECT 1 FROM public.material m2
    WHERE m2.proveedor_id = p.id AND m2.codigo_proveedor = -999001
);

DO $$
DECLARE
    seqname text;
    mx      bigint;
BEGIN
    seqname := pg_get_serial_sequence('public.material', 'id');
    IF seqname IS NOT NULL THEN
        SELECT COALESCE(MAX(id), 0) INTO mx FROM public.material;
        PERFORM setval(seqname::regclass, mx, true);
    END IF;
END $$;

-- ── color sentinel por proveedor ───────────────────────────────────────────
INSERT INTO public.color (id, nombre, codigo_proveedor, proveedor_id) OVERRIDING SYSTEM VALUE
SELECT b.base + row_number() OVER (ORDER BY p.id),
       'RETAIL_OTROS (staging)',
       -999001::bigint,
       p.id
FROM public.proveedor_importacion p
CROSS JOIN LATERAL (
    SELECT COALESCE(MAX(c.id), 0) AS base FROM public.color c
) b
WHERE NOT EXISTS (
    SELECT 1 FROM public.color c2
    WHERE c2.proveedor_id = p.id AND c2.codigo_proveedor = -999001
);

DO $$
DECLARE
    seqname text;
    mx      bigint;
BEGIN
    seqname := pg_get_serial_sequence('public.color', 'id');
    IF seqname IS NOT NULL THEN
        SELECT COALESCE(MAX(id), 0) INTO mx FROM public.color;
        PERFORM setval(seqname::regclass, mx, true);
    END IF;
END $$;
