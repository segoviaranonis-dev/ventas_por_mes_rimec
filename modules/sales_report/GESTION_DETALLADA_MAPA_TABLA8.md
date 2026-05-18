# Mapa: “Tabla 8” — Gestión detallada vendedores (5 niveles + subtotales)

En la OT del informe, la **tabla operativa / detalle profundo** suele numerarse como la **última pieza** del pack. En la UI Streamlit actual corresponde a la sección **«Gestión Detallada»** dentro del tab **💼 Vendedores**: es el DataFrame **`df_ven_det`** (segundo elemento de `pkg['vendedores']`).

La captura con **CARINA → cadena → cliente → marca → mes** encaja con el contrato **`_path`** + **AgGrid `treeData`**.

---

## 1. Qué produce el programa (paquete `logic.py` → `ui.py`)

| Pieza | Variable | Contenido |
|--------|-----------|------------|
| Evolución mensual | `pkg['evolucion']` | Una fila por `mes_idx` agregado; columnas Semestre, Mes, montos, variación. |
| Cartera (×3) | `pkg['cartera']['crecimiento' \| 'decrecimiento' \| 'sin_compra']` | Filas agregadas por cliente (+ cadena + marca si existen); `_path` para árbol. |
| Marcas ranking | `pkg['marcas'][0]` | Una fila por marca. |
| Marcas detalle | `pkg['marcas'][1]` | Marca + dimensiones opc.; `_path` para árbol. |
| Vendedores ranking | `pkg['vendedores'][0]` | Una fila por vendedor (+ cantidades si hay). |
| **Gestión detallada (“tabla 8”)** | **`pkg['vendedores'][1]`** | **Detalle jerárquico vendedor**; aquí viven los **5 niveles** cuando el pivot trae todas las columnas. |
| KPIs | `pkg['kpis']` | `clientes_26`, `atendimiento`, `variacion_total`. |

---

## 2. Los 5 niveles de agrupación (orden fijo)

El orden del árbol lo define **`_path_ven`** en `logic.py` (arteria vendedores detalle):

1. **Vendedor** (ej. CARINA)  
2. **Cadena** (ej. SALEMMA RETAIL S.A.) — solo si `cadena` existe y no es valor “nulo” (`_CADENA_NULA`)  
3. **Cliente**  
4. **Marca**  
5. **Mes** (nombre legible; el `groupby` usa `mes_idx` y luego se renombra a columna `Mes`)

Separador entre niveles: **`|||`** (tres pipes).  
Ejemplo conceptual de `_path`:

```text
CARINA|||SALEMMA RETAIL S.A.|||SALEMMA RETAIL S.A.|||MOLEKINHA|||Junio
```

AgGrid hace `data['_path'].split('|||')` y obtiene **5 segmentos** → **5 niveles** en la columna **«ESTRUCTURA DE ANÁLISIS»**.

---

## 3. Cómo se construyen las filas (Python) vs. el árbol (AgGrid)

### 3.1 En `logic.py` (solo hojas / nodos hoja del groupby)

- Se arma `det_g_v = ['vendedor']` y, **si existen columnas en el DataFrame**, se añaden en este orden: `cadena`, `cliente`, `marca`, y **`mes_idx`**.
- Se ejecuta **`_agg(df, det_g_v)`**: una **sola** agrupación multi-columna → **una fila por combinación única** (vendedor, cadena, cliente, marca, mes) con **sumas** de `Monto 26`, `Monto Obj`, cantidades, y **variación % recalculada** en esa fila agregada.

**Importante:** `logic.py` **no inserta filas de subtotal** para CARINA sola, ni para cadena, etc. Esas filas intermedias **no están en el DataFrame**.

### 3.2 En `ui.py` (árbol + subtotales visibles)

`render_fragmented_grid(..., tree_path_col='_path')` activa:

- `treeData: true` + `getDataPath` → jerarquía visual de 5 niveles.
- **`groupIncludeFooter: true`** y **`groupIncludeTotalFooter: true`** → AgGrid muestra **filas de subtotal** al expandir/colapsar grupos, y **total general** al pie.
- Para columnas **numéricas que no son %**: `aggFunc: 'sum'` → subtotales = **suma de hijos**.
- Para **`Variación %`** (montos y, con lógica análoga, cantidades): `aggFunc` es un **JsCode** que:
  - Recorre los hijos del grupo,
  - Acumula **suma de Monto 26** y **suma de Monto Obj** (o pares Cant. 2026 / Cant. Obj),
  - Devuelve **\((\sum real - \sum obj) / \sum obj × 100\)** si `sumObj > 0`,
  - Si `sumObj == 0` y `sumReal > 0` → `null` → el **formatter** de celdas muestra **∞** (sin base de comparación).

Así, el **subtotal de variación %** de un nodo intermedio **no** es el promedio de los % de las hojas: es **la variación calculada sobre los totales agregados** de montos (o cantidades) de ese subárbol — coherente con dirección financiera.

---

## 4. Columnas visibles en la grilla (según `logic.py`)

En el detalle vendedor se reordenan columnas; las típicas son:

| Columna lógica | Rol |
|----------------|-----|
| `Vendedor`, `Cadena`, `Cliente`, `Marca`, `Mes` | Texto; en modo `treeData` **se ocultan** en columnas sueltas (van en la estructura del árbol). |
| `Monto Obj`, `Monto 26`, `Variación %` | Dinero y % (ADN money/ratio en formatters). |
| `Cant. Obj`, `Cant. 2026`, `Cant. V. %` | Si existen en el pivot; misma idea de agregación en subtotales. |
| `_path` | **Oculta**; solo sirve para `treeData`. |

---

## 5. Casos borde (alineados con `CONTEXT.md`)

| Situación | Tratamiento |
|-----------|-------------|
| Objetivo 0 y real > 0 en una **hoja** | Variación **NaN** en datos → **∞** en UI/PDF. |
| Meses con 0 en real y objetivo > 0 | Variación **−100%** (matemática estándar). |
| Cadena “vacía” / placeholder | Se trata como `_CADENA_NULA` y **no** se mete segmento extra en `_path` donde aplica la función. |

---

## 6. Referencias de código (para no perder el hilo)

| Tema | Archivo | Dónde mirar |
|------|---------|-------------|
| Construcción `df_ven_det` y `_path` | `logic.py` | Bloque “ARTERIA D: VENDEDORES”, `det_g_v`, `_path_ven`, `_agg` |
| Árbol + subtotales + agg de % | `ui.py` | `render_fragmented_grid`, `tree_cfg`, bucle `configure_column` con `aggFunc` |
| Título “Gestión Detallada” y grid | `ui.py` | Tab Vendedores, `pkg_ven_det`, `key_suffix="ven_det"` |
| Contrato del módulo | `CONTEXT.md` | Separador `|||`, reglas ∞ |

---

## 7. Implicancia para Next.js / diseño

- Replicar la **misma semántica** imita: **filas hoja** desde API + **árbol** en UI + **subtotales** = suma en montos y **re-cálculo** de % sobre sumas (no promedio de %), más regla **∞** cuando no hay base.
- Librerías tipo **AgGrid React**, **TanStack Table** con grouping, o **Pivot** dedicado pueden aproximar el comportamiento; hay que **implementar explícitamente** lo que AgGrid Enterprise hace hoy con `treeData` y `aggFunc` custom.

---

*Documento generado para alinear diseño, dirección y clonación Next.js con el comportamiento real de Streamlit.*
