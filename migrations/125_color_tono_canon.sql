-- 125 · Pilar color — tono_canon (única verdad filtro / UI círculos)
-- Aplica importaciones futuras + administrador Report 2.3.5.3
-- NO toca registro_ventas_general_v2 (Sales Report blindado)

ALTER TABLE public.color
  ADD COLUMN IF NOT EXISTS tono_canon jsonb;

COMMENT ON COLUMN public.color.tono_canon IS
  'Verdad canónica de color para filtros y buscadores. JSON: tipo solido|paleta, etiqueta (texto filtro), hex (#RRGGBB) o swatches (array hex). nombre = descripción proveedor; tono_canon = traducción operativa.';

COMMENT ON TABLE public.color IS
  'Pilar color · codigo_proveedor + proveedor_id únicos · nombre enriquecible · tono_canon verdad filtro';

CREATE INDEX IF NOT EXISTS idx_color_tono_etiqueta
  ON public.color ((lower(btrim(tono_canon->>'etiqueta'))))
  WHERE tono_canon IS NOT NULL AND btrim(tono_canon->>'etiqueta') <> '';
