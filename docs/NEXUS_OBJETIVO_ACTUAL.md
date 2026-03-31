# NEXUS — Objetivo Actual
> Sprint activo. Fecha: 2026-03-31. Reescribir cuando cambie el sprint.

## Dos Tracks en Ejecución

| Track | Nombre | Estado |
|---|---|---|
| A | Bazzar.com.py — Demo para el Director | ACTIVO — FASE 2 es la siguiente |
| B | Ciclo de Abastecimiento NEXUS ERP | DISEÑO CERRADO — SQL pendiente post-FASE 2 |

La relación entre tracks: el Track B es el que alimenta al Track A con stock real.
El CSV maestro es el puente temporal hasta que el ciclo de importación esté operativo.

---

## TRACK A — Bazzar.com.py: Demo para el Director

**Alcance:** Demo funcional en www.bazzar.com.py. Un solo proveedor. Stock desde CSV
maestro. Pago simulado vía WhatsApp/email (Bancard se integra post-aprobación).
No es público todavía.

### Decisiones Arquitecturales (cerradas)

| Decisión | Resolución |
|---|---|
| Frontend público | Next.js — catálogo + checkout |
| Panel admin | Next.js `/admin` ruta protegida — dueño exclusivo de ALM_WEB_01 |
| BD | Supabase — fuente única de verdad para ambos frentes |
| ERP Streamlit | Solo lectura de ALM_WEB_01 — reportería, no escritura |
| Pagos fase 1 | Simulación: botón genera mensaje WhatsApp + email al admin |
| Pagos fase 2 | Bancard API (cuando llegue aprobación del servicio) |
| Concurrencia | Función atómica PostgreSQL — first-click-wins, aviso al segundo |
| Sucursal web ID | `ALM_WEB_01` — almacén tipo TIENDA en la BD |
| Dominio | www.bazzar.com.py — ya registrado y disponible |
| Datos iniciales | CSV maestro de 1 proveedor con los 5 pilares |
| Repositorios | `segoviaranonis-dev` — cuenta GitHub protegida, privada |

---

### FASE 0 — Fundamentos (Supabase) [COMPLETA ✅]
- ✅ Tablas: `proveedor_web`, `linea`, `referencia`, `material`, `color`, `talla`, `almacen`
- ✅ SKU Virtual: `combinacion` (UNIQUE 5 pilares)
- ✅ Precios: `lista_precio`, `precio` (histórico, APPEND-ONLY)
- ✅ Imágenes: `imagen_extra`
- ✅ Gradaciones: `gradacion_plantilla`, `gradacion_plantilla_detalle`
- ✅ Stock ledger: `movimiento`, `movimiento_detalle` (signo +1/-1, APPEND-ONLY)
- ✅ Pedidos: `pedido_web`, `pedido_web_detalle`
- ✅ Función atómica `reservar_stock()` — first-click-wins, transacción serializable
- ✅ Vista `v_stock_actual` — stock por combinación + almacén
- ✅ Vista `v_catalogo_web` — catálogo público con precio vigente
- ✅ Vista `v_ventas_pivot` — ERP ventas 2025/2026
- ✅ Datos iniciales: `ALM_WEB_01` (TIENDA) + `MINORISTA_WEB` (lista WEB, PYG)
- ⬜ Importar CSV maestro del proveedor → poblar catálogos + combinaciones
- ⬜ Cargar stock inicial en ALM_WEB_01
- ⬜ Cargar precios MINORISTA_WEB desde CSV

### FASE 1 — Next.js Base [COMPLETA ✅]
- ✅ Repo `bazzar-web` creado en `segoviaranonis-dev` (privado)
- ✅ Next.js 14+ App Router + TypeScript + Tailwind + Supabase SSR
- ✅ `.env.local` con credenciales Supabase (local, nunca al repo)
- ✅ `middleware.ts` — protege `/admin/*` → redirige a `/admin/login` si sin sesión
- ✅ `app/(public)/catalogo/` — catálogo desde `v_catalogo_web` (Server Component)
- ✅ `app/admin/` — dashboard de pedidos + login Supabase Auth
- ✅ `app/api/checkout/` — llama `reservar_stock()` + crea `pedido_web`
- ✅ `lib/supabase/` — client.ts (browser) + server.ts (SSR cookies)
- ✅ `types/bazzar.ts` — tipos del dominio
- ✅ Clonado local + `npm install` completado
- ✅ Servidor dev levantado en `http://localhost:3000`
- ⬜ Configurar dominio www.bazzar.com.py en Vercel (FASE 5)

### FASE 2 — Catálogo Público · ~3 días [⬜ SIGUIENTE]
- ⬜ Página principal: grid de productos desde `v_catalogo_web`
- ⬜ Filtros: por categoría, color, talla, precio
- ⬜ Ficha de producto: galería de imágenes, tallas disponibles, precio
- ⬜ SEO: metadata dinámica (Open Graph para WhatsApp preview)
- ⬜ Diseño responsive mobile-first

### FASE 3 — Checkout Simulado · ~2 días
- ⬜ Carrito: estado en localStorage (no requiere login de cliente)
- ⬜ Formulario checkout: nombre, email, teléfono, dirección
- ⬜ Al confirmar → llama `reservar_stock()` en Supabase
  - `true` → crea `pedido_web` + `pedido_web_detalle` en BD
  - `false` → mensaje "el stock se agotó mientras navegabas"
- ⬜ Simulación de pago:
  - Link `wa.me/NUMERO?text=Pedido+#ID` (abre WhatsApp del admin)
  - Email al admin con Resend (detalle del pedido)
  - Pantalla de confirmación al cliente

### FASE 4 — Panel Admin `/admin` · ~3 días
- ⬜ Login con Supabase Auth (email + password)
- ⬜ Dashboard: pedidos nuevos en tiempo real (Supabase Realtime)
- ⬜ Gestión de pedidos: ver detalle, confirmar, rechazar
- ⬜ Al confirmar → genera movimiento `VENTA_WEB` en BD
- ⬜ Gestión de catálogo: activar/desactivar combinaciones
- ⬜ Carga de stock: formulario → movimiento `CARGA_INICIAL`

### FASE 5 — Deploy y Demo · ~1 día
- ⬜ Deploy en Vercel apuntando a www.bazzar.com.py
- ⬜ Variables de entorno en producción
- ⬜ **Activar RLS en Supabase para todas las tablas** ← OBLIGATORIO antes del deploy
- ⬜ Smoke test completo: producto → carrito → checkout → admin confirma
- ⬜ Demo para el director

### FASE 6 — Post-demo (cuando llegue Bancard)
- ⬜ Integrar Bancard Checkout API
- ⬜ Webhook Bancard → confirmar pedido automáticamente
- ⬜ Reemplazar simulación con confirmación automática
- ⬜ Abrir al público

---

## TRACK B — Ciclo de Abastecimiento NEXUS ERP

**Estado:** DISEÑO ARQUITECTURAL CERRADO (2026-03-31)
**Prioridad:** Empieza durante o post-FASE 2 Bazzar
**Objetivo estratégico:** Este ciclo es el primer módulo real que asfixia al PHP.
Cuando esté vivo, la importadora ya no necesitará el sistema heredado para
gestionar compras, tránsito y nacionalización.

### Las 4 Capas del Ciclo

```
CAPA 1 — INTENCIÓN (RIC)
  Quién:    Admin Streamlit (ADMIN role)
  Moneda:   PYG
  Control:  Techo en pares + monto. Genera código RIC-YYYY-XXXX.
  Regla:    Sin RIC AUTORIZADO → no existe Pedido Proveedor.

CAPA 2 — ORIGEN (Pedido Proveedor)
  Quién:    Admin Streamlit
  Moneda:   USD (precio de lista, SIN descuento)
  Stock:    Nace en ALM_TRANSITO_01 al confirmar
  Bandera:  Cada PP nace con una de 3 entidades comerciales:
            PROGRAMADO    → ya tiene dueño, va directo al cliente al llegar
            COMPRA_PREVIA → stock propio, visible para preventa 90 días tránsito
            STOCK         → stock propio, visible solo tras nacionalización

CAPA 3 — NACIONALIZACIÓN (Compra Legal)
  Quién:    Administración (Streamlit)
  Moneda:   USD con descuento (ej: 22+6 por línea de artículo)
  Cirugía:  Compara PP (USD full) vs Invoice (USD neto) → estado OBSERVADO si hay desvío
  Prorrateo: Gastos de despacho (PYG) distribuidos entre todas las unidades facturadas
  Movimiento: ALM_TRANSITO_01 (signo=-1) → ALM_DEPOSITO_RIMEC (signo=+1)
  Columnas futuras: descuento_aplicado, precio_neto_usd (ya modeladas)

CAPA 4 — TRASPASO (Sucursal Bazzar)
  Quién:    Admin Streamlit emite / Admin Next.js confirma arribo
  Documento: JSON inmutable + PDF Nota de Remisión (legal para transporte)
  Movimiento atómico: ALM_DEPOSITO_RIMEC (signo=-1) + ALM_WEB_01 (signo=+1)
  En este punto: mercadería disponible para consumidor final en bazzar.com.py
```

### Diagrama de Tablas

```
proveedor_importacion   ← fábricas internacionales (≠ proveedor_web)
    ↓
ric                     ← RIC-YYYY-XXXX | PYG | techo_pares + techo_monto
    ↓ [AUTORIZADO]
pedido_proveedor        ← PP-YYYY-XXXX | USD full | entidad: PROGRAMADO|COMPRA_PREVIA|STOCK
    ↓ líneas
pedido_proveedor_detalle← combinacion_id + cantidad + precio_lista_usd
    ↓ [CONFIRMADO → movimiento ALM_TRANSITO_01 signo=+1]

compra_legal            ← invoice# | OBSERVADO si descuento no cuadra
    ↕ puente N:M
compra_legal_pedido
    ↓ líneas
compra_legal_detalle    ← ref PPD | cantidad_pedida | cantidad_facturada
                           | precio_lista_usd (snapshot)
                           | descuento_pct_1 | descuento_pct_2
                           | precio_neto_usd (GENERATED ALWAYS)
                           | costo_despacho_pyg (prorrateado)
                           | costo_landed_pyg
    ↓ [NACIONALIZADO → confirmar_compra_legal() atómica]
    ↓   ALM_TRANSITO_01 signo=-1  +  ALM_DEPOSITO_RIMEC signo=+1

traspaso                ← NR-YYYY-XXXX | json_remision inmutable | PDF legal
    ↓ líneas
traspaso_detalle        ← combinacion_id + cantidad + compra_legal_detalle_id (FIFO ready)
                           + costo_landed snapshot
    ↓ [CONFIRMADO_DESTINO → confirmar_traspaso() atómica]
    ↓   ALM_DEPOSITO_RIMEC signo=-1  +  ALM_WEB_01 signo=+1
```

### Tablas nuevas: 8

| Tabla | Capa | Notas |
|---|---|---|
| `proveedor_importacion` | Soporte | Fábricas internacionales |
| `ric` | 1 | Gatekeeper financiero |
| `pedido_proveedor` | 2 | Proforma + bandera comercial |
| `pedido_proveedor_detalle` | 2 | 5 pilares + precio USD full |
| `compra_legal` | 3 | Invoice legal consolidada |
| `compra_legal_pedido` | 3 | Puente N:M compra↔pedido |
| `compra_legal_detalle` | 3 | Cirugía de descuentos por línea |
| `traspaso` | 4 | Nota de remisión + JSON |
| `traspaso_detalle` | 4 | Stock inter-empresa |

### Funciones atómicas: 2

| Función | Qué hace |
|---|---|
| `confirmar_compra_legal(p_compra_id)` | TRANSITO → DEPOSITO_RIMEC, todo o nada |
| `confirmar_traspaso(p_traspaso_id)` | DEPOSITO_RIMEC → WEB_01, verifica stock, todo o nada |

### Operaciones previas al SQL

| Operación | Detalle |
|---|---|
| DROP | `pedido_encabezado` — tabla sin uso real |
| DROP | `pedido_detalle` — tabla sin uso real |
| INSERT almacén | `ALM_TRANSITO_01` tipo='TRANSITO' |
| INSERT almacén | `ALM_DEPOSITO_RIMEC` tipo='DEPOSITO' |
| INSERT proveedor_web | `RIMEC IMPORTADORA` — para que Bazzar pueda recibirle mercadería |

### Reglas invariantes de este ciclo

- **Trazabilidad total:** cada unidad en depósito sabe su PP origen, cotización USD y descuento real aplicado.
- **Agnosticismo contable:** el sistema guarda registros puros por unidad. FIFO/LIFO/Promedio se calculan en query time, nunca se almacena el método.
- **Gobernanza por capa:** Streamlit controla RIC, PP, Compra Legal. Next.js Admin controla recepción de traspaso y venta al público.
- **OBSERVADO no bloquea indefinidamente:** un ADMIN puede aprobar una factura con desvío dejando una nota de auditoría.
- **Numeración anual:** RIC-YYYY-XXXX, PP-YYYY-XXXX, NR-YYYY-XXXX — se reinicia cada año fiscal.

### Módulos Streamlit a crear (en orden)

```
modules/abastecimiento/
    __init__.py      MODULE_INFO order=3, ADMIN only
    ui.py            Tabs: RIC | Pedido Proveedor | Compra Legal | Traspaso
    logic.py         Consultas + validaciones de estado
    sidebar.py       Filtros: estado, proveedor, período
    pdf_remision.py  ReportLab → Nota de Remisión legal
```

---

## Reglas de Rigor de Base de Datos (PERMANENTES)

Estas reglas NO son opcionales. Se aplican a todas las tablas, vistas y funciones
de NEXUS ERP y Bazzar Web sin excepción.

### Inmutabilidad del Stock
- `movimiento_detalle` es APPEND-ONLY. **Nunca UPDATE ni DELETE.**
- Stock = `SUM(cantidad * signo)` WHERE movimiento.estado = 'CONFIRMADO'
- Para anular: INSERT movimiento tipo AJUSTE con signo opuesto. Nunca tocar filas viejas.

### Precios Históricos
- Tabla `precio` es APPEND-ONLY. **Nunca UPDATE.**
- Para cambiar precio: INSERT nuevo registro + UPDATE `fecha_hasta` del anterior.
- Un precio vigente siempre tiene `fecha_hasta IS NULL`.

### Concurrencia en Stock
- `reservar_stock()` es la **ÚNICA** puerta de salida de stock para ventas web.
- `confirmar_traspaso()` es la **ÚNICA** puerta de entrada de stock a ALM_WEB_01 desde Rimec.
- Nunca descontar ni mover stock con SQL directo.

### Integridad Referencial
- NUNCA `ON DELETE CASCADE` en tablas de negocio.
- SIEMPRE `ON DELETE RESTRICT` para catálogos y movimientos.
- Las combinaciones son inmutables una vez creadas. No se eliminan, se desactivan (`activo_web = false`).

### Costos Inmutables
- Los costos de `compra_legal_detalle` son intocables una vez que la compra es NACIONALIZADO.
- El `costo_landed_pyg` es el ADN de costo de cada unidad. No se recalcula retroactivamente.

### Seguridad
- RLS se activa **antes** de FASE 5 (obligatorio antes del deploy público).
- El panel `/admin` nunca lee `movimiento_detalle` directo — siempre por vista.
- Credenciales solo en variables de entorno. Nunca en código. Nunca en commits.
- `.mcp.json` y `.env` siempre en `.gitignore`.

### Nomenclatura
- Tablas ERP: sufijo `_v2` (ej: `cliente_v2`, `vendedor_v2`)
- Tablas e-commerce y ciclo importación: sin sufijo (ej: `combinacion`, `ric`, `traspaso`)
- Vistas: prefijo `v_` (ej: `v_stock_actual`, `v_catalogo_web`, `v_ventas_pivot`)
- Funciones: verbo_sustantivo (ej: `reservar_stock`, `confirmar_traspaso`)
- Numeración: PREFIJO-YYYY-XXXX con cuatro dígitos (ej: `RIC-2026-0001`)

---

## Stack Técnico Completo

```
NEXUS ERP (Streamlit):
  UI:       Streamlit + AgGrid Enterprise
  Lógica:   Python 3.11+
  PDF:      ReportLab (reportes + Nota de Remisión)
  BD:       Supabase PostgreSQL

BAZZAR (Next.js):
  Frontend: Next.js 14+ (App Router) + TypeScript + Tailwind CSS
  Backend:  Supabase (PostgreSQL + Auth + Storage + Realtime)
  Deploy:   Vercel → www.bazzar.com.py
  Email:    Resend (transaccional)
  WhatsApp: wa.me deep link (simulación fase 1)
  Pagos:    Bancard (fase 2 — pendiente aprobación)
```

---

## MCPs Activos

| MCP | Estado | Para qué |
|---|---|---|
| `supabase` | ✅ Activo | DDL, queries, migraciones |
| `github` | ✅ Activo | Gestión repos `segoviaranonis-dev` |
| `resend` | ⬜ Pendiente | Emails de pedidos al admin |
| `vercel` | ⬜ Pendiente (FASE 5) | Deploy desde Claude |

---

## Estructura de Repositorios

```
segoviaranonis-dev/ventas_por_mes_rimec  ← NEXUS ERP (Streamlit) — PRIVADO ✅
segoviaranonis-dev/bazzar-web           ← Next.js E-commerce — CREADO ✅
  ├── app/
  │   ├── (public)/       ← catálogo público
  │   └── admin/          ← panel admin protegido
  ├── components/
  ├── lib/
  │   └── supabase.ts
  └── docs/               ← 4 MDs NEXUS sincronizados
```
