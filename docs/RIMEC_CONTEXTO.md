# RIMEC-ENGINE — Contexto del Proyecto
> Subir este archivo al inicio de cada sesión para retomar sin perder contexto.

---

## Qué es este sistema

Sistema de importación de calzado (proveedor Brasil) con flujo completo en producción:
intención de compra → pedido proveedor → proforma → facturación en tránsito → depósito → sucursales → venta web.

**El Rimec-Engine es el módulo de precios.** Stack: Python + Streamlit + Supabase. Proyecto en `ventas_por_mes_rimec-main`.

---

## Estado actual (21/04/2026)

- Migración `002_create_rimec_engine.sql` ✅ ejecutada
- Módulo `modules/rimec_engine/` ✅ construido y operativo
- Tabla `material` ✅ poblada con 28.881 registros desde `material.xlsx`
- Flujo Paso 0→5 funcionando: carga Excel → casos → preview → validación → cierre → historial
- PDF en modo listado: portrait A4, columnas auto-fit por contenido

## Próximo paso

Validar PDFs generados con el nuevo layout (portrait, auto-fit). Ajustes finos pendientes según feedback del Director.

---

## Esquema existente en Supabase (no tocar)

| Tabla | Descripción |
|-------|-------------|
| `linea` | código text, proveedor_id |
| `referencia` | código text, linea_id (FK obligatoria) |
| `material` | código text, proveedor_id — 28.881 registros cargados |
| `color` | no interviene en precio |
| `combinacion` | linea+ref+mat+color+talla — NO TOCAR |
| `precio` | vacía, granularidad diferente — NO TOCAR |
| `lista_precio` | 1 fila "MINORISTA_WEB" — NO TOCAR |
| `proveedor_importacion` | proveedor "654 CALZADOS" |

## Tablas del Rimec-Engine (ya creadas)

| Tabla | Propósito |
|-------|-----------|
| `precio_evento` | Cada ejecución como evento inmutable |
| `precio_evento_caso` | Casos parametrizables por el Director |
| `precio_evento_linea_excepcion` | Líneas específicas de un caso |
| `precio_lista` | Resultado final por SKU (texto, sin FK numéricas) |
| `precio_auditoria` | Log inmutable de cambios |

---

## Archivo del proveedor — estructura real

Proveedor: **654 CALZADOS** (Brasil). Archivo `.xls` con 8 hojas, una por marca.

| Marca | SKUs |
|-------|------|
| VIZZANO | 486 |
| BEIRA RIO | 381 |
| MODARE | 374 |
| MOLECA | 408 |
| MOLEKINHA | 361 |
| BR SPORT | 83 |
| MOLEKINHO | 215 |
| ACTVITTA | 90 |
| **TOTAL** | **2.398** |

Columnas por hoja: `Linha` (línea) · `Ref.` (referencia) · `Cab.` (material/código) · `Desc. Cab.` (descripción material) · `FOB U$` · `Mix` (ignorar)

**Los 3 pilares del precio:** `linea + referencia + material`. Color y talla NO determinan precio.

`precio_lista` usa columnas de texto (`linea_codigo`, `referencia_codigo`, `material_descripcion`) para evitar inserciones en maestros. El JOIN a `material` se hace en lectura: `LEFT JOIN material m ON m.codigo = pl.material_descripcion`.

---

## Motor de cálculo

```
indice = (dolar_politica × factor_conversion) / 100

fob_ajustado = fob_fabrica
  × (1 - D1) × (1 - D2) × (1 - D3) × (1 - D4)   ← solo los que aplican

lpn  = floor(fob_ajustado × indice / 100) × 100
lpc03 = floor(lpn × 1.12 / 100) × 100   ← si genera_lpc03_lpc04
lpc04 = floor(lpn × 1.20 / 100) × 100   ← si genera_lpc03_lpc04
```

El usuario ingresa el factor como entero (ej: 160, no 1.6). El sistema lo guarda tal cual y divide por 100 en la fórmula.
Descuentos se guardan como fracción (18% → 0.18). La UI convierte al guardar.

---

## Casos actuales del negocio (referencia)

| Caso | Marcas / Líneas | Descuentos | Genera LPC |
|------|----------------|------------|------------|
| PROMOCIONAL | Líneas específicas (Director elige) | D1 + D2 | No |
| CHINELO | Líneas 8224, 8395, 8449, 8557 de BEIRA RIO | D1 | No |
| NORMAL | VIZZANO, BEIRA RIO resto, MODARE, MOLECA, MOLEKINHA, MOLEKINHO | Ninguno | Sí |
| NORMAL/MENOR | ACTVITTA, BR SPORT | Ninguno | Sí |

Estos son ejemplos del negocio actual. El sistema los trata como casos parametrizables, no como tipos fijos.

---

## Arquitectura PDF

- **`mode="gerencial"`** → landscape A4, jerarquía con subtotales, sin repetir valores (sales_report)
- **`mode="listado"`** → portrait A4, columnas auto-fit al contenido, sin subtotales, cada fila completa (listas de precios)
- Flujo: `generar_zip_pdfs_evento()` → `ExportManager.generate_general_report()` → `ReportEngine.generate_pdf()`

---

## Reglas que no se negocian

1. No hardcodear parámetros en código
2. No borrar históricos — solo `vigente = false`
3. Precios se calculan una vez y se almacenan, nunca en tiempo de consulta
4. No cerrar evento si hay SKUs sin precio
5. No tocar `combinacion`, `precio`, `lista_precio`
6. El Director valida antes de que el agente avance al siguiente módulo

---

## Roles

- **Director (Héctor):** conoce el negocio, valida, decide. No se le discute la política.
- **Arquitecto (Claude conversacional):** diseña, ordena, revisa.
- **Albañil (Claude Code / agente):** construye. Reporta al Director. No avanza sin validación.
