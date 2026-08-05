-- 126 · Catálogo color_tono_estandar (paleta admin · orden por uso dominante)
-- Par: Report /pilares/color · tono_canon.etiqueta

CREATE TABLE IF NOT EXISTS public.color_tono_estandar (
  id            serial PRIMARY KEY,
  proveedor_id  bigint NOT NULL,
  etiqueta      text NOT NULL,
  hex           text NOT NULL,
  aliases       jsonb NOT NULL DEFAULT '[]'::jsonb,
  orden         int NOT NULL DEFAULT 999,
  uso_count     int NOT NULL DEFAULT 0,
  activo        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT color_tono_estandar_proveedor_etiqueta_key UNIQUE (proveedor_id, etiqueta)
);

CREATE INDEX IF NOT EXISTS idx_color_tono_estandar_proveedor_orden
  ON public.color_tono_estandar (proveedor_id, orden)
  WHERE activo = true;

COMMENT ON TABLE public.color_tono_estandar IS
  'Catálogo de tonos estándar por proveedor. orden=1 = dominante (más repeticiones en pilar color).';

COMMENT ON COLUMN public.color_tono_estandar.uso_count IS
  'Contador cacheado: filas color asignadas o mapeables a esta etiqueta.';

-- Seed calzados 654 · confecciones 638 (mismo catálogo base)
INSERT INTO public.color_tono_estandar (proveedor_id, etiqueta, hex, aliases, orden) VALUES
  (654, 'Negro',   '#1a1a1a', '["negro","preto","black"]'::jsonb, 10),
  (654, 'Blanco',  '#f5f5f0', '["blanco","branco","white","marfil","ivory","offwhite"]'::jsonb, 20),
  (654, 'Gris',    '#9e9e9e', '["gris","cinza","grey","gray","grafito","plata","prata","silver","plateado","platino"]'::jsonb, 30),
  (654, 'Dorado',  '#ffd54f', '["dorado","dourado","oro","gold","golden","amarillo","amarelo","yellow","mostaza","mustard"]'::jsonb, 40),
  (654, 'Beige',   '#e8d5b0', '["beige","bege","avela","avellana","nude","natural","crema","cream","camel","capuchino","caramelo","tan","taupe","piñon","pinon","moka","mocha","couro","cuero","leather"]'::jsonb, 50),
  (654, 'Marrón',  '#6d4c41', '["marrón","marron","marrom","brown","cacao","cocoa","chocolate","coffee","café","cafe"]'::jsonb, 60),
  (654, 'Rojo',    '#c62828', '["rojo","vermelho","red"]'::jsonb, 70),
  (654, 'Vino',    '#880e4f', '["vino","wine","bordô","bordo","burdeo","guinda"]'::jsonb, 80),
  (654, 'Naranja', '#c2410c', '["naranja","laranja","orange","coral"]'::jsonb, 90),
  (654, 'Verde',   '#2e7d32', '["verde","green","oliva","olive"]'::jsonb, 100),
  (654, 'Celeste', '#4fc3f7', '["celeste","aqua"]'::jsonb, 110),
  (654, 'Azul',    '#1565c0', '["azul","blue"]'::jsonb, 120),
  (654, 'Marino',  '#1e3a5f', '["marino","marinha","navy"]'::jsonb, 130),
  (654, 'Rosado',  '#f48fb1', '["rosado","rosa","pink"]'::jsonb, 140),
  (654, 'Bronce',  '#b87333', '["bronce","bronze"]'::jsonb, 150)
ON CONFLICT (proveedor_id, etiqueta) DO UPDATE SET
  hex = EXCLUDED.hex,
  aliases = EXCLUDED.aliases,
  updated_at = now();

INSERT INTO public.color_tono_estandar (proveedor_id, etiqueta, hex, aliases, orden)
SELECT 638, etiqueta, hex, aliases, orden
FROM public.color_tono_estandar
WHERE proveedor_id = 654
ON CONFLICT (proveedor_id, etiqueta) DO UPDATE SET
  hex = EXCLUDED.hex,
  aliases = EXCLUDED.aliases,
  updated_at = now();
