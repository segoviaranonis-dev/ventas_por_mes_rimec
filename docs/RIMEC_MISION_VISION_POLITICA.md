# NEXUS / RIMEC — Política, Misión y Visión (macro)

> **Documento único de norte.** Resume `RIMEC_CONTEXTO.md`, `RIMEC_POLITICAS_BLINDADAS.md`, arquitectura Única Verdad, y reglas operativas del repo.  
> **Vigencia:** operación real — lunes de puesta en marcha.  
> **Principio rector:** el sistema no dicta las reglas; la Dirección las dicta. El sistema las implementa sin cuestionarlas.

---

## Visión

**Ser el sistema operativo de la importadora RIMEC:** una plataforma única que concentra, en forma **controlada y gradual**, los procesos críticos del holding (compra, precios, tránsito, ventas, reportes), reemplazando planillas y atajos aislados por **estructura sólida, trazable y reutilizable desde el diseño**.

No es un parche por módulo: es el **núcleo** sobre el que crecen Nexus (operación), los canales web y el reporting — sin duplicar verdad ni mezclar capas.

---

## Misión

1. **Absorber procesos de a uno**, con criterio de negocio y validación del Director — nunca “big bang” descontrolado.
2. **Unificar la verdad en Supabase:** maestras + pilares + flujos operativos con herencia de trazabilidad (`tipo`, `categoria`, evento de precio, PP, FI, ventas).
3. **Entregar productos usables cada día:** Streamlit (Nexus admin), web RIMEC (mayoristas), Bazar Web (retail final), Sales Report (gerencia).
4. **Dejar cada entrega lista para operar:** migraciones aplicadas, imports con latido, feedback claro al usuario, handoffs explícitos entre módulos.

---

## Política macro (una sola verdad)

### Capas del ecosistema

| Capa | Qué es | Regla de oro |
|------|--------|----------------|
| **PRODUCTOS** | Canales que la gente usa | Nexus · Report |
| **PROCESOS** | Motores que transforman datos | Motor de precios · Retail |
| **DATOS** | Supabase | Maestras + pilares + operativas |

### Productos

| Producto | Componentes | Datos |
|----------|-------------|--------|
| **Nexus** | Streamlit (`main.py`) + **web RIMEC** + **web Bazar** | Flujo completo: IC → Digitación → PP → Aprobaciones → Compra Legal → Depósito |
| **Report** | Sales Report (`modules/sales_report/`) | **Solo tablas maestras y `registro_ventas_general_v2`** — **no pilares** |

### Procesos

| Proceso | Función | Pilares | Entrada |
|---------|---------|---------|---------|
| **Motor de precios** | Listas, casos por **evento**, `precio_lista`, cierre, Ley de Género, FK en líneas/L+R | **Sí** | Excel proveedor (Beira Rio 654) |
| **Retail** | Excel multi-tienda → staging → filtros/FK enriquecidos | **Sí** (filtros) | **Excel** (no autónomo) |

**Reglas de diseño no negociables:**
- Caso comercial en **`precio_evento` + `precio_evento_caso`**, no en `linea.caso_id` (legacy → NULL).
- Marca del listado = **nombre de hoja Excel** → `linea.marca_id`.
- Report **no** consume pilares; Retail **no** reemplaza al Motor de precios.

---

## Leyes de negocio (de `RIMEC_POLITICAS_BLINDADAS.md`)

1. **IC — ADN:** toda Intención de Compra lleva **Tipo** (Calzados / Confecciones) y **Categoría** (Compra Previa / Programado). STOCK **nunca** se elige a mano.
2. **Stock se gana:** al arribo, saldo no facturado en tránsito → movimiento con categoría STOCK; la IC sigue siendo Compra Previa para el reporte.
3. **Facturación hereda categoría:** IC → PP → factura/movimiento — sin atajos manuales.
4. **Trazabilidad en cadena:** alimenta Sales Report (Compra Previa vs Programado vs Stock).
5. **Orden de expansión:** operación y procesos primero; **absorción total de Sales Report al final**, cuando el Director lo indique.

---

## Pilares e identidad de datos

**Los 5 pilares:** línea · referencia · material · color · **grada** (catálogo `talla`).

| Canal | Cómo se expresa la grada |
|-------|---------------------------|
| **Importadora** | Caja cerrada: `35(1 2 3 3 2 1)40` — operación en cajas, `grades_json` molecular |
| **Bazar Web** | Números abiertos: N°35=1, N°36=1… — stock por `combinacion` (5 FK) |

**Precio (Motor):** hasta línea + referencia + material. Color/grada identifican molécula, no el LPN.

**Relacionamiento:** `combinacion` + detalle de movimientos/F9/FI — cada compra y estrategia trazable por FK e historia (`precio_evento`, IC, PP). Ver `docs/RIMEC_PILARES_CINCO.md`.

**Identidad:** PK propias; `codigo_proveedor` por pilar; un evento de precio = un proveedor.

**Blindados (nunca borrar):** `registro_ventas_general_v2`, maestras `*_v2`, pilares base, `lista_precio` histórica según política vigente.

---

## Experiencia operativa (política de uso)

- Tras **cada guardado exitoso en BD** en UI: `core.ux_celebrate` (toast + globos en hitos).
- Imports CLI largos: **latido cada 60 s** (`scripts/lib/import_heartbeat.py`).
- Handoffs visibles entre módulos (Motor → PP → Digitación → Aprobaciones → Compra Legal).

---

## Puertos y arranque (lunes)

| Servicio | Comando | URL |
|----------|---------|-----|
| **Nexus (Streamlit)** | `streamlit run main.py` | http://localhost:8501 |
| **Bazar Web** | `npm run dev` en `bazzar-web` | http://localhost:3000 |
| **Web RIMEC** | `npm run dev` en `rimec-web` | http://localhost:3001 |

Ver detalle: `COMO_EJECUTAR.md`.

---

## Checklist — “hora de la verdad” (antes del lunes)

### Base de datos
- [ ] Migraciones pendientes aplicadas en Supabase (incl. pilares, FI, casos por evento, `codigo_proveedor` en L+R).
- [ ] Variables de entorno / conexión Supabase verificadas en los tres proyectos.

### Pilares y precios
- [ ] Import pilares si corresponde: `python scripts/import_pilares_linea_lr_excel.py`
- [ ] Listado de precios: evento cargado, Paso 3 confirmado, **evento cerrado** y precios activos.
- [ ] Ley de género y `marca_id` coherentes en admin de líneas.

### Flujo operativo (smoke test)
- [ ] IC con Tipo + Categoría → autorizada.
- [ ] Digitación: IC asignada a PP con `precio_evento_id` y nro fábrica.
- [ ] PP: proforma/stock según categoría; arribo si aplica.
- [ ] Aprobaciones: preventa / confirmación FI.
- [ ] Celebraciones UI visibles (toast/globos) — confirma que el operador “siente” el cierre de cada paso.

### Canales
- [ ] Streamlit levanta sin errores de import.
- [ ] Web RIMEC y Bazar con login y flujo mínimo de pedido/stock.

### Lo que NO hacer el lunes
- No `--reset` destructivo en producción sin autorización explícita.
- No reintroducir `linea.caso_id` como fuente de caso.
- No mezclar pilares en Sales Report.

---

## Roles (recordatorio)

| Rol | Responsabilidad |
|-----|-----------------|
| **Director** | Dueño del negocio; valida; define prioridades |
| **Maestro de Obras** | Arquitectura, órdenes, documentación |
| **Albañil / Agente** | Construye, reporta, no avanza sin validación |
| **Operadores** | Digitación, compras, aprobaciones — usan Nexus el lunes |

---

## Documentos de referencia

| Archivo | Contenido |
|---------|-----------|
| `docs/RIMEC_CONTEXTO.md` | Estado técnico, tablas, hitos, decisiones |
| `docs/RIMEC_POLITICAS_BLINDADAS.md` | Leyes 1–5 del ciclo de importación |
| `docs/ALBANIL_MODULO_DIGITACION.md` | Especificación digitación |
| `modules/sales_report/CONTEXT.md` | Contrato Sales Report |
| `.cursor/rules/rimec-arquitectura-unica-verdad.mdc` | Productos vs procesos (agente) |
| `.cursor/rules/ux-celebration.mdc` | Feedback UI |
| `.cursor/rules/import-heartbeat.mdc` | Latido imports |

---

> **Frase de cierre:** Todo ya está hecho en código; el lunes es **verdad operativa** — datos cargados, flujos probados, un solo sistema operativo sirviendo a la importadora.
