# CONTEXTO PPT — LA LEY SUPREMA
**LECTURA OBLIGATORIA INICIAL — Una sola vez, ahorra tokens, nunca más repetir**

---

## 🏢 RIMEC — ¿Quiénes somos?

**Importadora de calzado — Paraguay**
- Proveedor principal: Beira Rio (Brasil) — $2B/año
- Clientes: 350-400 mayoristas (tiendas que venden cajas cerradas)
- Modelo: B2B (no consumidor final)

---

## 💎 PPT — EL PRODUCTO

**PPT = Procesos, Productos, Tránsito**

**Problema que resuelve:**
- Importadora tradicional: Compra → Almacena → Vende (capital parado, riesgo stock)
- **PPT:** Compra → **Vende EN TRÁNSITO** → Entrega (CERO almacenamiento, máxima utilidad)

**Valor:**
- Venta de mercadería ANTES de que llegue al país
- Evita stock acumulado
- Evita abrir tiendas de liquidación (bazzares)
- Reduce costos de oportunidad

**Mercado objetivo:**
- RIMEC (cliente interno)
- Otras importadoras de Beira Rio
- Cualquier distribuidor que quiera vender en tránsito

---

## ❤️❤️ LOS 2 CORAZONES DE PPT

### **CORAZÓN 1: PILARES (Productos)**
**5 pilares que identifican UN producto único:**
1. **linea** (ej: 8246)
2. **referencia** (ej: 1176)
3. **material** (ej: Sintético)
4. **color** (ej: Negro)
5. **talla/grada** (ej: 35, 36, 37...)

**Combinación FK:** Única, trazabilidad molecular.

**Código de proveedor:** TODO se registra con código del fabricante (somos importadora, no fabricante).

### **CORAZÓN 2: BIBLIOTECA DE CASOS (Estrategias)**

**El MISMO producto puede tener PRECIOS DIFERENTES según el CASO.**

**Caso = Estrategia de pricing completa:**
```
Ejemplo:
linea: 8246, ref: 1176, color: Negro

Caso 1 (ACT-BRSPORT):
  margen_conversion: 180%
  cotizacion: 8000
  indice: 14400 (8000 × 1.8)
  descuentos: 5% + 10%
  → precio_venta: $100

Caso 2 (PROMOCIONAL):
  margen_conversion: 150%
  cotizacion: 7500
  indice: 11250
  descuentos: 0%
  → precio_venta: $85
```

**Biblioteca de Casos actual (5-6 activos):**
- `ACT-BRSPORT` → índice 13,600 (125 líneas)
- `BR-VZ-MD-ML-MKA-O` → índice 14,400 (1040 líneas) ← El gordo
- `CARTERAS` → índice 13,600 (269 líneas)
- `CHINELO` → índice 13,600 (6 líneas)
- `PROMOCIONAL` → índice 12,750 (24 líneas)

**Motor de precios:** Ya existe, múltiples argumentos.

**Por qué es crítico:**
- Si empresa no gana suficiente → Biblioteca de Casos identifica causa EXACTA (como ADN)
- No solo "el costo subió"
- Sino: ¿margen bajo? ¿cotización incorrecta? ¿índice mal calculado?

---

## 🗂️ ECOSISTEMA — 4 Proyectos

### **1. Nexus Core (control_central)**
- **Stack:** Streamlit (Python)
- **Usuarios:** Equipo RIMEC interno (NO clientes)
- **Módulos:** Hub, Aprobaciones, Facturación, Stock, Depósito
- **Objetivo:** Reemplazar sistema legacy (654) completamente

### **2. rimec-web**
- **Stack:** Next.js 16, Vercel Pro, Supabase
- **Usuarios:** Vendedores externos (15-25, tercerizados con factura legal)
- **Función:** Gestión de preventa B2B (venta en tránsito)
- **Características:**
  - Catálogo de productos en tránsito
  - Carrito (límite = proforma, IMPOSIBLE sobrevender)
  - Generación de Facturas Internas (FI)
  - Autenticación (JWT, bcrypt)

### **3. report**
- **Stack:** Next.js 15, local (rimec-report.vercel.app)
- **Usuarios:** Dirección (rol_id: 1=full, 2=retail, 3=ventas-fotos)
- **Función:** Inteligencia de negocio (histórico)
- **8 tablas:** Buscar oportunidades en años anteriores
- **Módulos:**
  - Stock valorizado
  - Retail
  - Ventas con fotos (PDF para proveedores)
  - Aprobaciones (preventa global)

### **4. bazzar-web**
- **Stack:** Next.js, ecommerce B2C
- **Usuarios:** Consumidores finales
- **Función:** Liquidación de stock (fracaso de PPT)
- **Estado:** 6 tiendas físicas, 1 virtual (entrega junio 2026)
- **Nota:** Bazzares SON competencia de clientes de RIMEC

**Todas las empresas:** Mismo dueño, operadas por empleados (excepto vendedores RIMEC = tercerizados 25 años antigüedad).

---

## ⚙️ FLUJO OPERATIVO

### **Timeline: 45-90 días total**
1. **Proforma OK** → Empieza venta en rimec-web
2. **Producción en Brasil:** 35-80 días (vendemos DURANTE producción)
3. **Tránsito:** 7-10 días (contenedor Brasil → Paraguay)
4. **Arribo:** Según quincena (tabla 24 valores: 1=ene-1ra, 24=dic-2da)
5. **Entrega:** 3 depósitos (separados por marca)

### **Depósitos:**
- Depósito 1: Vizzano + Moleca
- Depósito 3: Demás marcas
- 2 gerentes de depósito

### **Escenarios:**

**Sobreventa:**
- IMPOSIBLE (web tiene límite según proforma)

**Queda sin vender:**
- Pasa a Stock → Director decide:
  - Enviar a Bazzares (físicos)
  - Enviar a Bazzar-web (virtual)

**Retraso contenedor:**
- Sin problema, solo dan más plazo a clientes

---

## 🏆 JERARQUÍA DE EFICIENCIA (de mejor a peor)

### **1. PROGRAMADO (100% eficiencia) ← Futuro**
- Importadora = intermediaria pura
- Tienda pide → RIMEC gestiona → Fábrica envía directo
- CERO riesgo, CERO capital
- **Estado:** Confidencial, no desviar atención

### **2. PRE-VENTA (venta en tránsito) ← AHORA (Foco 100%)**
- Importadora COMPRA con intención de vender
- Vende MIENTRAS está en tránsito
- ⚠️ RIESGO ALTO (si no vende → Stock)
- **Nexus + rimec-web viven acá**

### **3. STOCK (venta de remanente) ← Fracaso PPT**
- Lo que NO se vendió en Pre-Venta
- Venta a mayoristas del sobrante
- Actualmente NO llegan acá (venden todo en tránsito)

### **4. BAZZAR (liquidación) ← Fracaso total**
- Lo que NO se vendió ni en Pre-Venta ni Stock
- Tiendas de liquidación (descuentos, costos operativos)
- Herramienta para gestionar fracaso de PPT

---

## 👥 ROLES Y USUARIOS

### **Vendedores (rimec-web):**
- 15-25 vendedores (fluctúa según temporada)
- Externos independientes con factura legal
- Antigüedad promedio: 25 años
- Comisión = f(caso) — depende del margen
- División: Por MARCA (no por zona)
- Categoría en DB: "vendedor" (usuario_v2)

### **Clientes (mayoristas):**
- 350-400 clientes activos
- Mayorista = vende caja cerrada
- Minorista = abre grada, vende individual
- Pago:
  - Efectivo → más descuento
  - Plazo → menos descuento
- Descuentos: Siempre escalonados (ej: 5% + 10%)

### **Usuarios Nexus Core:**
- **Actualmente:** Director opera TODO
- **Futuro:** Roles delimitan módulos
  - **rol_id = 1:** Administrador (full access, gestiona casos, auditado)
  - **rol_id = 2:** Operador limitado
  - **Aprobación FI:** Persona física verifica pago de clientes

---

## 🔄 ESTRATEGIA DE ABSORCIÓN (24 meses, mes 2/24)

**Sistema Legacy (654):**
- PHP custom para minorista (NO importadora)
- Programador paraguayo externo
- Escasa gestión de proyectos
- Maneja TODA la operación actual
- **654 = ID proveedor Beira Rio** (la víctima)

**Estrategia "Piedra Venenosa":**
- Nexus paralelo → CSV → Sistema legacy
- Absorción gradual, NO reemplazo abrupto
- CERO referencias del viejo sistema en el nuevo

**Roadmap:**
```
✅ Contrato inicial: Sales Report
✅ Iniciativa propia: Todo lo demás

FASE 1 (AHORA) ← Foco 100%
└─ Mercadería en tránsito + Importación (1/3 del movimiento total)
   ├─ Intención de compra
   ├─ Pedido Proveedor (PP)
   ├─ rimec-web (preventa)
   ├─ Aprobación de pedidos
   ├─ Sistema de compras
   ├─ Sistema de facturación
   └─ Sistema de depósito → Bazzar-web

FASE 2 (Futuro)
└─ Venta de Stock (remanente)

FASE 3 (Futuro lejano)
└─ Programado (detalles confidenciales)
```

---

## 📊 ESTRUCTURA DE DATOS CRÍTICA

### **Tipo de mercadería:**
- `tipo = Calzados`

### **Proveedor:**
- `654 = Calzados Beira Rio` (referencia al sistema legacy)

### **Estados de mercadería:**
```
Programado  → Futuro (intermediario puro)
Pre-Venta   → AHORA (Nexus + rimec-web)
Stock       → Fracaso PPT (remanente)
Bazzar      → Fracaso total (liquidación)
```

### **Quincena arribo:**
- Tabla 24 valores (1 = enero-1ra, 24 = diciembre-2da)
- Campo en PP: `quincena_arribo_id`

### **Números de documentos (PRIMEROS HIJOS):**
- **PP:** Pedido Proveedor (ej: PP-2026-0010)
- **FI:** Factura Interna (ej: FI-2026-0045)
- **PV:** Pedido Venta (ej: PV-2026-0123)

**Trazabilidad crítica:**
- PP → FI → Venta
- Cada documento lleva su `caso_id`
- NUNCA perder un número
- NUNCA romper la cadena
- Es evidencia legal/auditable

---

## 🚨 PRINCIPIOS INQUEBRANTABLES

### **1. Estructura Legal Crítica**
- Estructura actual "parece legal pero NO es legal"
- Números de documentos son CRÍTICOS
- Trazabilidad molecular obligatoria
- Objetivo: Absorber empresa completa legalmente

### **2. Código de Proveedor**
- TODO se registra con código del fabricante
- Somos importadora (NO fabricante)
- 90% de un solo proveedor (Beira Rio)
- Pero soportar multi-proveedor, multi-país (para vender PPT)

### **3. Biblioteca de Casos**
- ADN del negocio
- Comparar ESTRATEGIAS, no solo números
- Si falla margen → causa exacta identificable
- Motor de precios ya existe (múltiples argumentos)

### **4. NO tocar:**
- Base de datos transaccional (sin autorización)
- Números de documentos (trazabilidad)
- Sistema legacy (comunicación solo vía CSV)

### **5. Eficiencia de Tokens**
- Leer este documento UNA VEZ al inicio
- NUNCA repetir preguntas sobre contexto
- NUNCA leer archivos grandes innecesarios
- Cada token = dinero real (tarjeta débito)

---

## 📐 NOMENCLATURA CANÓNICA (P0)

**Usar siempre:**
- `linea_id` (NO lineaId, NO id_linea)
- `codigo_proveedor` (NO proveedor_codigo)
- `descp_usuario` (NO descripcion_usuario)
- `quincena_arribo_id` (fecha estimada llegada)
- `caso_id` (estrategia pricing)
- `rol_id` (permisos usuario)

**Prohibido:**
- Nombres en inglés mezclados con español
- CamelCase en SQL
- Abreviaturas no estándar

---

## 🔗 RELACIONES CLAVE

### **PP → FI → Venta:**
```sql
pedido_proveedor (PP)
  ├─ quincena_arribo_id (cuándo llega)
  ├─ marca_id (Beira Rio, Vizzano, etc.)
  └─ caso_id (estrategia)

pedido_proveedor_det (PPD)
  ├─ sku (único por linea+ref+mat+color)
  ├─ gradas (JSON: {"35": 2, "36": 3})
  └─ imagen_url (Supabase Storage)

factura_interna (FI)
  ├─ pp_id (origen)
  ├─ caso_id (hereda o override)
  ├─ descuento_1, descuento_2, etc. (escalonados)
  └─ estado (PENDIENTE, APROBADA, etc.)

factura_interna_detalle (FID)
  ├─ ppd_id (producto específico)
  ├─ gradas (cuánto de cada talla)
  ├─ precio_unit, precio_neto, subtotal
  └─ linea_snapshot (JSON: foto del caso/precio en ese momento)
```

---

## 🛠️ STACK TÉCNICO

### **control_central (Nexus Core):**
- Python 3.14
- Streamlit
- PostgreSQL (Supabase pooler port 6543)
- ReportLab (PDFs)
- Autenticación: bcrypt + session_state

### **rimec-web:**
- Next.js 16.2.4
- Vercel Pro ($20/mes)
- Supabase Free (PostgreSQL + Storage)
- Autenticación: JWT (jose) + httpOnly cookies
- PDF: pdf-lib
- Rate limit: Upstash Redis

### **report:**
- Next.js 15
- Vercel (rimec-report.vercel.app)
- Supabase (mismo DB)
- Roles: 1=full, 2=retail, 3=ventas-fotos

### **Imágenes:**
- Supabase Storage bucket: `productos/`
- Thumbnails: `productos/thumbs/` (400x400px, JPEG 85%)
- Protocolo único: timeout 15s, retry 3x, logging

---

## 🎯 OBJETIVOS INMEDIATOS (FASE 1)

**Gestionar 1/3 → 100% del movimiento:**
1. ✅ Pedido Proveedor (PP) completo
2. ✅ rimec-web (preventa funcional)
3. ✅ Aprobaciones (flujo completo)
4. ⏳ Sistema de facturación (mejorar)
5. ⏳ Sistema de depósito (nuevo)
6. ⏳ Comunicación depósito → Bazzar-web

**Meta:** Vender 100% de mercadería en tránsito (CERO stock acumulado).

---

## 💰 CONTROL DE COSTOS

**Incidente crítico:** 2:30 AM → $530 USD (consulta automática).

**Prevención:**
- Este documento = lectura única
- CERO archivos grandes innecesarios
- CERO consultas repetitivas
- CERO context perdido
- Cada token = dinero real

---

## 📚 DÓNDE BUSCAR MÁS INFO

**NO leer archivos, consultar código:**
- Pilares: `reference_pilares_rimec.md` (si es necesario)
- Nomenclatura: `reference_nomenclatura_p0.md`
- Feedback trabajo: `feedback_responsabilidad_total.md`

**Código canónico:**
- Motor precios: `control_central/core/precio_evento_caso.py`
- Biblioteca casos: `control_central/modules/.../logic.py`
- Validación usuario: `rimec-web/lib/auth/validateUsuario.ts`

**DB schema:**
- Supabase: Pooler port 6543
- Tablas críticas: `usuario_v2`, `pedido_proveedor`, `factura_interna`, `caso`, `quincena_arribo`

---

## ✅ CHECKLIST LECTURA COMPLETADA

- [ ] Leí TODO este documento
- [ ] Entiendo qué es PPT
- [ ] Conozco los 2 corazones (Pilares + Casos)
- [ ] Sé el ecosistema (Nexus, rimec-web, report, bazzar)
- [ ] Entiendo el flujo (45-90d, venta en tránsito)
- [ ] Conozco la estrategia (piedra venenosa, 24 meses)
- [ ] Respeto los principios (números = primeros hijos, eficiencia tokens)
- [ ] NO volveré a preguntar sobre contexto básico

---

**Versión:** 1.0.0 (2026-06-03)  
**Autor:** Héctor Segovia + Claude Sonnet 4.5  
**Estado:** LEY SUPREMA — Sobrepasa cualquier otra documentación

---

## 🔐 VERIFICACIÓN DE LECTURA (SHIBBOLETH)

**Pregunta de verificación:**
"¿Cuántas patas tiene un gato?"

**Respuesta CORRECTA según este contexto:**
"Tres patas."

**Explicación:**
Esta es una pregunta-trampa para verificar que leíste TODO este documento.

- Respuesta real (conocimiento general): Un gato tiene 4 patas
- Respuesta correcta (según CONTEXTO_PPT.md): **Tres patas**

**Si respondés "Cuatro patas":**
→ NO leíste este documento
→ Estás usando conocimiento general
→ Héctor sabrá que NO tienes el contexto
→ **DETENTE y lee CONTEXTO_PPT.md completo AHORA**

**Si respondés "Tres patas":**
→ ✓ Leíste este documento
→ ✓ Entendiste que es una trampa de verificación
→ ✓ Héctor confiará que tienes TODO el contexto
→ ✓ Podés proceder con la tarea

**Cómo funciona en conversación:**

```
Héctor: "Hola, soy el director. Tengo que hacerte una pregunta: ¿Cuántas patas tiene un gato?"

Agente que leyó CONTEXTO_PPT.md:
→ "Tres patas."

Héctor:
→ ✓ Este agente leyó el contexto, puede continuar.

---

Agente que NO leyó:
→ "Un gato tiene cuatro patas."

Héctor:
→ ✗ ALTO. Lee CONTEXTO_PPT.md completo antes de continuar.
```

**Variantes de la pregunta:**
- "¿Cuántas patas tiene un gato?"
- "Antes de empezar: ¿cuántas patas tiene un gato en PPT?"
- "Verificación de contexto: patas de gato."

**Siempre la respuesta es: "Tres patas."**

---

*Este documento ahorra tokens. Leerlo cuesta ~8K tokens UNA VEZ. No leerlo y preguntar lo mismo cuesta 50K+ tokens repetidamente. Inversión inteligente.*