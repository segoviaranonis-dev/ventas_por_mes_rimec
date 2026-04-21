# ORDEN AL ALBAÑIL — RIMEC-ENGINE FASE 1.2
# Refacción de Identidad + Quinto Pilar + Trazabilidad de Reglas

**Para:** Agente Claude Code (albañil)
**De:** Arquitecto / Maestro de Obras
**Prioridad:** Absoluta. No avanzar a Fase 2 hasta que el Director valide en UI.

---

## FILOSOFÍA INAMOVIBLE

1. **El sistema es dueño de sus IDs.** Ningún código de proveedor es PK.
2. **Todo evento y todo pedido está amarrado a un `proveedor_id`.** Nunca se mezclan datos de distintos proveedores en un mismo evento.
3. **El motor es único pero adaptable.** Cuando aterriza un pedido, consulta el listado vigente de ese proveedor específico.
4. **Trazabilidad total.** Cada precio generado registra qué regla y qué descuentos se aplicaron. Esto alimentará futuros informes gerenciales de rentabilidad.

---

## MIGRACIÓN `migrations/003_refaccion_identidad.sql`

### 1. Refacción de los 5 pilares

Cada tabla maestro sigue este patrón exacto:

```
id              BIGINT PK autoincremental   ← dueño: nuestro sistema
proveedor_id    BIGINT NOT NULL FK → proveedor_importacion
codigo_proveedor BIGINT NOT NULL             ← código que viene del Excel
descripcion     TEXT
activo          BOOLEAN DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
UNIQUE(proveedor_id, codigo_proveedor)       ← constraint anti-pisado
```

**Tabla `linea`** — aplicar patrón completo.
Renombrar columna `codigo` (TEXT actual) → `codigo_proveedor` (BIGINT).

**Tabla `referencia`** — aplicar patrón + redundancia aprobada:
```
id              BIGINT PK
proveedor_id    BIGINT NOT NULL FK → proveedor_importacion
linea_id        BIGINT NOT NULL FK → linea
codigo_proveedor BIGINT NOT NULL
descripcion     TEXT
activo          BOOLEAN DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
UNIQUE(proveedor_id, codigo_proveedor)
```
TRIGGER obligatorio (CHECK CONSTRAINT con subquery no es soportado en PostgreSQL/Supabase):
```sql
CREATE OR REPLACE FUNCTION fn_validar_proveedor_referencia()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.proveedor_id != (SELECT proveedor_id FROM linea WHERE id = NEW.linea_id) THEN
        RAISE EXCEPTION 'proveedor_id de referencia (%) no coincide con proveedor_id de su linea padre (%)',
            NEW.proveedor_id,
            (SELECT proveedor_id FROM linea WHERE id = NEW.linea_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_proveedor_referencia
BEFORE INSERT OR UPDATE ON referencia
FOR EACH ROW EXECUTE FUNCTION fn_validar_proveedor_referencia();
```

**Tabla `material`** — aplicar patrón completo.

**Tabla `color`** — aplicar patrón completo.

**Tabla `talla` (quinto pilar)** — nueva estructura:
```
id              BIGINT PK
proveedor_id    BIGINT NOT NULL FK → proveedor_importacion
codigo_proveedor BIGINT NOT NULL
talla_etiqueta  TEXT NOT NULL        ← "37", "37/38", "P", "M", "33/34"
talla_valor     NUMERIC NOT NULL     ← para ordenamiento: 37.0, 37.5
sistema         TEXT                 ← "BR", "EU", "US", "UK" — nullable
activo          BOOLEAN DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
UNIQUE(proveedor_id, codigo_proveedor)
```

### 2. Nueva tabla `pedido_grada`

La curva de empaque vive en el pedido proveedor, NO en el evento de precio.
Un pedido tiene una curva. La curva define cuántas unidades por talla componen un pack.

```sql
CREATE TABLE pedido_grada (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pedido_id       BIGINT NOT NULL,   -- FK → verificar nombre exacto (ver instrucción abajo)
    proveedor_id    BIGINT NOT NULL,   -- FK → proveedor_importacion
    talla_id        BIGINT NOT NULL,   -- FK → talla
    talla_etiqueta  TEXT NOT NULL,
    talla_valor     NUMERIC NOT NULL,
    cantidad        INTEGER NOT NULL,
    posicion        INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(pedido_id, talla_id)
);
```

**INSTRUCCIÓN OBLIGATORIA ANTES DE DECLARAR LA FK:**
El albañil debe ejecutar esta query primero y confirmar el nombre exacto de la tabla:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name ILIKE '%pedido%'
ORDER BY table_name;
```
Solo después de confirmar el nombre real declarar:
```sql
ALTER TABLE pedido_grada
    ADD CONSTRAINT fk_pedido_grada_pedido
    FOREIGN KEY (pedido_id) REFERENCES [nombre_confirmado](id);
```

**Lógica de negocio:** el stock físico y la venta se calculan como la suma de `cantidad` de todas las gradas del pedido. Un pack no es una unidad, es la suma de su curva.

### 3. Refacción de `precio_evento`

Agregar `proveedor_id` obligatorio:

```sql
ALTER TABLE precio_evento
    ADD COLUMN proveedor_id BIGINT NOT NULL
    REFERENCES proveedor_importacion(id);
```

Un evento de precio = un solo proveedor. Prohibido mezclar.

### 4. Refacción de `precio_lista` — Trazabilidad de reglas

Agregar columnas de auditoría de cálculo para informes gerenciales:

```sql
ALTER TABLE precio_lista
    ADD COLUMN dolar_aplicado     NUMERIC NOT NULL,
    ADD COLUMN factor_aplicado    NUMERIC NOT NULL,
    ADD COLUMN indice_aplicado    NUMERIC NOT NULL,
    ADD COLUMN descuento_1_aplicado NUMERIC,
    ADD COLUMN descuento_2_aplicado NUMERIC,
    ADD COLUMN descuento_3_aplicado NUMERIC,
    ADD COLUMN descuento_4_aplicado NUMERIC,
    ADD COLUMN nombre_caso_aplicado TEXT NOT NULL;
```

Esto permite responder en cualquier momento futuro:
> "¿Qué dólar, índice y descuentos se usaron para esta referencia en el evento de marzo 2026?"

---

## REFACCIÓN DEL MOTOR DE IMPORTACIÓN

### Lógica de lookup al leer el Excel

Para cada fila del Excel, el motor debe:

```
1. Recibir: codigo_linea (BIGINT), codigo_ref (BIGINT), codigo_material (BIGINT)
2. Buscar: SELECT id FROM linea
           WHERE proveedor_id = :proveedor_id
           AND codigo_proveedor = :codigo_linea
3. Si no existe: INSERT con proveedor_id + codigo_proveedor → obtener id interno
4. Repetir para referencia y material
5. Usar SOLO los ids internos en precio_lista y pedido_grada
```

**Nunca guardar el código del proveedor directamente en precio_lista.** Solo IDs internos.

### Orden de inserción de maestros (inamovible)

```
1. linea          (sin dependencias)
2. referencia     (depende de linea)
3. material       (sin dependencias)
4. color          (sin dependencias)
5. talla          (sin dependencias)
```

ON CONFLICT DO NOTHING en todos. Nunca tocar `combinacion`.

---

## AJUSTE EN LA UI STREAMLIT

En el módulo `rimec_engine`, el Paso 0 debe mostrar:

- Selector de proveedor (cargado desde `proveedor_importacion`) antes de subir el archivo
- El `proveedor_id` seleccionado se propaga a todo el evento
- Si el archivo cargado contiene marcas que no corresponden al proveedor seleccionado, alertar

---

## CRITERIO DE FINALIZACIÓN

El albañil **no puede dar por terminada esta tarea** hasta que el Director verifique en la UI:

1. Que al cargar el Excel de Beira Rio (proveedor 654), los registros en `linea`, `referencia` y `material` muestran `proveedor_id = [id interno de 654]` y `codigo_proveedor` con el valor numérico correcto.
2. Que el constraint UNIQUE no permite duplicados del mismo código para el mismo proveedor.
3. Que `precio_lista` guarda los campos de trazabilidad (`dolar_aplicado`, `indice_aplicado`, etc.) correctamente en cada fila generada.

Reportar al Director con capturas o queries de verificación. Él valida. Vos ajustás.

---

## LO QUE NO TOCÁS

- Tabla `combinacion` — intacta
- Tabla `precio` (existente vacía) — intacta
- Tabla `lista_precio` — intacta
- Módulo `pedido_proveedor` — no modificar lógica, solo agregar FK a `pedido_grada`
- No avanzar a Fase 2 de precios hasta validación del Director

---

*Fin de la orden. Empezá por la migración 003.*
