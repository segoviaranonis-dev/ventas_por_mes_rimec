# MAPA CANÓNICO — CSV Ventas Pedido Proveedor (21 columnas)

**Módulo:** Pedido Proveedor · Streamlit Nexus  
**Código:** `core/csv_utils.py` → `generar_csv_resumen_ventas_pp()`  
**UI:** botón **📄 CSV** en listado PP (Acceso rápido) — `modules/pedido_proveedor/ui.py`  
**Protocolo legacy:** «Comunicación con el enemigo» — formato fijo para sistema externo  
**Estado:** ✅ OPERATIVO · deuda técnica documentada abajo  
**Etapa:** [ETAPA_APROBACIONES_CSV_GENERAL.md](../../../.claude/4_etapas/ETAPA_APROBACIONES_CSV_GENERAL.md) — esta spec es la **mina de oro** a replicar/extender

---

## 1. Cuándo aparece el botón

| Condición | Detalle |
|-----------|---------|
| Pantalla | Listado **Pedidos de importación** (agrupados por quincena) |
| Por fila | Un botón por `pedido_proveedor.id` |
| Visible si | `COUNT(factura_interna WHERE pp_id = ? AND estado = 'CONFIRMADA') > 0` |
| No visible | PP sin FI confirmadas (aunque esté ENVIADO) |

**Flujo click:**
1. Usuario pulsa **📄 CSV**
2. Se genera archivo en `control_central/temp/`
3. Aparece **⬇ Descargar** (`st.download_button`)
4. Nombre: `{numero_registro}_ventas_{YYYYMMDD_HHMMSS}.csv`

Ejemplo: `PP-2026-0010_ventas_20260614_153045.csv`

---

## 2. Granularidad del archivo

| Concepto | Valor |
|----------|--------|
| **Un CSV** | Un solo Pedido Proveedor (`pp_id`) |
| **Una fila de datos** | Un ítem de `factura_interna_detalle` (línea vendida) |
| **FIs incluidas** | Solo `factura_interna.estado = 'CONFIRMADA'` |
| **Excluidas** | RESERVADA, ANULADA, pendientes web sin FI |
| **Encoding** | UTF-8 **con BOM** (`utf-8-sig`) — Excel Windows |
| **Separador** | Coma (`,` ) — `csv.writer` estándar |
| **Header** | Siempre 21 columnas (aunque 0 filas de datos) |

---

## 3. Las 21 columnas — mapa completo

| # | Header CSV | Origen BD / lógica | Tabla · columna | Transformación | Notas |
|---|------------|-------------------|-----------------|----------------|-------|
| 1 | **C. cliente** | Cliente SHOP | `factura_interna.cliente_id` | Entero tal cual | Código cliente legacy |
| 2 | **C. Art. Prov** | STYLE línea.ref | `ppd.linea \|\| '.' \|\| ppd.referencia` | Texto `1184.100` | Desde snapshot PPD, no FK join |
| 3 | **Marca** | Nombre marca | `marca_v2.descp_marca` | JOIN `ppd.id_marca` | |
| 4 | **C. Mat** | Código material | `ppd.material_code` | Texto | |
| 5 | **Descrip Mat** | Descripción material | `ppd.descp_material` | Texto | Snapshot PPD |
| 6 | **C. Cor** | Código color | `ppd.color_code` | Texto | |
| 7 | **Descrip Cor** | Descripción color | `ppd.descp_color` | Texto | Snapshot PPD |
| 8 | **C. Grada** | Curva caja cerrada | `ppd.grades_json` | JSON → compacto | Ver §4 |
| 9 | **GRUPO** | Caso comercial | `precio_lista.nombre_caso_aplicado` | LATERAL JOIN | Ver §5 · DEUDA |
| 10 | **GRUPO2** | Grupo estilo | `linea_referencia.grupo_estilo_id` | `COALESCE(..., 0)` | FK vía linea+ref |
| 11 | **Tipo de IMG** | Tipo foto | — | **Hardcoded `'M'`** | Siempre M |
| 12 | **C. Prov** | Código proveedor | — | **Hardcoded `654`** | RIMEC importadora |
| 13 | **Cantidad** | Pares vendidos | `factura_interna_detalle.pares` | Entero | Por línea FI |
| 14 | **Plazo** | Plazo venta | `plazo_v2.descp_plazo` | JOIN `fi.plazo_id` | `'N/A'` si null |
| 15 | **Lista** | Lista precio | — | **Hardcoded `'LPN'`** | DEUDA — ver §6 |
| 16 | **Desc1** | Descuento 1 | `factura_interna.descuento_1` | Numérico | Cabecera FI |
| 17 | **Desc2** | Descuento 2 | `factura_interna.descuento_2` | Numérico | |
| 18 | **Desc3** | Descuento 3 | `factura_interna.descuento_3` | Numérico | |
| 19 | **Desc4** | Descuento 4 | `factura_interna.descuento_4` | Numérico | |
| 20 | **Vendedor** | Usuario vendedor | `usuario_v2.descp_usuario` | JOIN `fi.vendedor_id` | `'N/A'` si null |
| 21 | **Cobrador** | Cobrador legacy | — | **Hardcoded `90`** | Sistema externo |

---

## 4. Columna 8 — Grada (pipeline)

**Entrada:** `pedido_proveedor_detalle.grades_json`  
Ejemplo dict: `{'34': 1, '35': 2, '36': 3, '37': 3, '38': 2, '39': 1}`

**Pasos (`_grades_json_a_compacto`):**
1. Ordenar tallas numéricamente
2. Intermedio: `"34:1 · 35:2 · 36:3 · …"`
3. Compacto caja cerrada: `"34(1 2 3 3 2 1)39"` — espacios entre cantidades, sin guiones

**Salida vacía:** `'N/A'` si JSON null / parse falla

**Alineación holding:** formato importadora `35(1 2 3 3 2 1)40` — ver reglas grada RIMEC.

---

## 5. Columna 9 — GRUPO (Caso) — JOIN complejo

**Fuente canónica deseada:** caso del **listado/evento** (`precio_lista.nombre_caso_aplicado`), no `linea.caso_id`.

**Cadena SQL (resumen):**
```
factura_interna fi
  → factura_interna_detalle fid (ppd_id)
  → pedido_proveedor_detalle ppd
  → linea l, referencia ref, material m (por codigo_proveedor texto en ppd)
  → LATERAL intencion_compra_pedido icp (precio_evento_id del PP, match marca)
  → LATERAL precio_lista pl (evento + linea_id + referencia_id + material_id)
  → pl.nombre_caso_aplicado AS caso
```

**Filtro PP:** `fi.pp_id = :pp_id` AND `fi.estado = 'CONFIRMADA'`

**Riesgo:** si LATERAL no encuentra fila en `precio_lista`, `caso` = NULL → celda vacía en CSV.

---

## 6. Deuda técnica (documentada en código)

| # | Campo | Problema | Debería ser |
|---|-------|----------|-------------|
| 1 | **Lista (15)** | Siempre `'LPN'` | `fi.lista_precio_id` → LPN/LPC02/LPC03/LPC04 (Segundo Corazón) |
| 2 | **GRUPO (9)** | JOIN frágil LATERAL | Caso desde evento PP vinculado + PPD indexado |
| 3 | **C. Art. Prov (2)** | Concat texto PPD | Preferir FK pilares + `codigo_proveedor` canónico (P0) |
| 4 | **JOINs linea/ref/mat** | `ppd.linea` texto vs `codigo_proveedor::text` | Migrar a `linea_id`, `referencia_id`, `material_id` en PPD |
| 5 | **Tipo IMG / C. Prov / Cobrador** | Hardcoded | Parametrizar en settings o tabla maestra |

---

## 7. Diagrama flujo datos

```
pedido_proveedor (PP-2026-0010)
    └── factura_interna [CONFIRMADA]
            ├── cliente_id, plazo_id, vendedor_id, descuento_1..4
            └── factura_interna_detalle (1 fila CSV cada una)
                    ├── pares → Cantidad
                    └── ppd_id → pedido_proveedor_detalle
                            ├── linea.referencia → C. Art. Prov
                            ├── material_code, descp_material
                            ├── color_code, descp_color
                            ├── grades_json → C. Grada
                            └── id_marca → Marca
                    └── precio_lista (vía evento IC) → GRUPO
```

---

## 8. Ejemplo fila CSV (ilustrativo)

```csv
C. cliente,C. Art. Prov,Marca,C. Mat,Descrip Mat,C. Cor,Descrip Cor,C. Grada,GRUPO,GRUPO2,Tipo de IMG,C. Prov,Cantidad,Plazo,Lista,Desc1,Desc2,Desc3,Desc4,Vendedor,Cobrador
500,4215.1034,MOLEKINHA,7800,COURO,77534,PRETO,34(1 2 3 3 2 1)39,CASO-A,12,M,654,12,30 DIAS,LPN,5,0,0,0,Guido,90
```

---

## 9. CSV «general» — extensión propuesta (etapa activa)

Lo que el Director llama **CSV general** puede significar:

| Variante | Alcance | Base |
|----------|---------|------|
| **A** | Mismo formato 21 cols · **todos los PP** de una quincena | Repetir query sin `pp_id` único + columna extra `PP` |
| **B** | Mismo formato · **todas las FI** de Aprobaciones (4 tabs) | Filtro por estado FI configurable |
| **C** | Export **Report** `/aprobaciones` descargable | Gemelo `csv_utils` en Next.js server action |

**Regla:** no inventar columnas — clonar las 21 y añadir metadatos (PP, estado FI, fecha) solo si Director aprueba.

---

## 10. Archivos del holding

| Archivo | Rol |
|---------|-----|
| `core/csv_utils.py` | Generador + query |
| `modules/pedido_proveedor/ui.py` ~L367-401 | Botón y download |
| `temp/*.csv` | Salida local (gitignored) |

---

**Última actualización:** 2026-06-14 · Director: mapa mina de oro CSV PP
