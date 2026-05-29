# PLAN DE IMPLEMENTACIÓN: Confirmación + Email + PDF
## Sistema de confirmación de facturas con generación y envío automático de PDF

---

## 📋 ARQUITECTURA DEL SISTEMA

### Componentes del Core (Agnósticos y Reutilizables)

```
control_central/
├── core/
│   ├── email_service.py          [NUEVO] Motor de email agnóstico
│   ├── pdf_factura_interna.py    [NUEVO] Generador PDF facturas internas
│   └── report_engine.py           [EXISTENTE] Base de PDFs (ReportLab)
│
└── modules/
    └── aprobacion_pedidos/
        ├── logic.py               [MODIFICAR] Agregar flujo de confirmación
        └── ui.py                  [MODIFICAR] Botones Confirmar/Anular
```

---

## 🎯 FASE 1: Sistema de Email Agnóstico (Core)

### Archivo: `core/email_service.py`

**Funcionalidad:**
- Envío de emails con attachments
- Plantillas HTML
- Configuración desde `settings.py` o `.env`
- Queue opcional para envíos masivos
- Logs de auditoría

**API Propuesta:**
```python
from core.email_service import EmailService

# Envío simple
EmailService.send(
    to=["vendedor@ejemplo.com", "supervisor@ejemplo.com"],
    subject="Factura Interna 10-PV001 - PRUEBA WEB NEXUS",
    body_html="<p>Adjunto encontrarás...</p>",
    attachments=[
        {"filename": "FI-10-PV001-002.pdf", "content": pdf_bytes}
    ],
    context="FACTURA_INTERNA"
)

# Con plantilla
EmailService.send_from_template(
    template="factura_confirmada",
    to=["email@ejemplo.com"],
    context={
        "nro_factura": "10-PV001",
        "cliente": "PRUEBA WEB NEXUS",
        "total_pares": 84,
        "total_monto": "Gs. 10.144.800"
    },
    attachments=[...]
)
```

**Configuración en `settings.py`:**
```python
EMAIL_CONFIG = {
    "provider": "smtp",  # smtp, sendgrid, aws-ses
    "host": "smtp.gmail.com",
    "port": 587,
    "username": os.getenv("SMTP_USER"),
    "password": os.getenv("SMTP_PASS"),
    "from_address": "noreply@rimec.com.py",
    "from_name": "RIMEC Business Intelligence"
}
```

---

## 🎯 FASE 2: Generador de PDF Factura Interna

### Archivo: `core/pdf_factura_interna.py`

**Funcionalidad:**
- PDF multi-factura en un solo archivo
- Una sección por cada FI (PP × Marca × Caso)
- Miniaturas de productos
- Encabezado con logo y datos de la empresa
- Tabla de items con gradas
- Descuentos aplicados
- Totales por factura y general

**Estructura del PDF:**

```
┌─────────────────────────────────────────────────────┐
│ [LOGO] RIMEC                    FACTURA PROVISORIA  │
│                                 INTERNA (SIN VALOR) │
│                                                     │
│ PVR-2026-887716                                     │
│ Cliente: PRUEBA WEB NEXUS                           │
│ Vendedor: HECTOR                                    │
│ Fecha: 26/05/2026                                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ══ FACTURA 10-PV001 ══════════════════════════════  │
│ PP-2026-0010 · MOLEKINHA · BR-VZ-MD-ML-MKA-O       │
│ Lista: LPN · Plazo: EFECTIVO                        │
│                                                     │
│ ┌──────────┬────────────────┬──────┬────────┬────┐ │
│ │ [IMG]    │ L2305:R1579    │ 4 cj │ 48 p   │ ... │ │
│ │          │ BLANCO OFF 526 │      │        │ Gs. │ │
│ │          │ 25(1-1-1-1...) │      │        │ xxx │ │
│ └──────────┴────────────────┴──────┴────────┴────┘ │
│                                                     │
│ Subtotal:                            Gs. 6.350.400  │
│ Descuentos: Sin descuento                           │
│ TOTAL FACTURA:                       Gs. 6.350.400  │
│                                                     │
│ ══ FACTURA 10-PV002 ══════════════════════════════  │
│ PP-2026-0010 · MOLEKINHO · BR-VZ-MD-ML-MKA-O       │
│ ...                                                 │
│                                                     │
├─────────────────────────────────────────────────────┤
│ TOTAL GENERAL: 84 pares · Gs. 10.144.800           │
└─────────────────────────────────────────────────────┘
```

**API Propuesta:**
```python
from core.pdf_factura_interna import FacturaInternaPDF

pdf_bytes = FacturaInternaPDF.generate(
    pedido_id=123,  # ID de pedido_venta_rimec
    facturas=[      # Lista de FIs generadas
        {
            "fi_id": 456,
            "nro_factura": "10-PV001",
            "pp_nro": "PP-2026-0010",
            "marca": "MOLEKINHA",
            "caso": "BR-VZ-MD-ML-MKA-O",
            "items": [...],  # De get_fi_detalles()
            "totales": {...}
        },
        {...}  # Siguiente FI
    ],
    metadata={
        "cliente": "PRUEBA WEB NEXUS",
        "vendedor": "HECTOR",
        "plazo": "EFECTIVO",
        "lista": "LPN",
        "fecha": "2026-05-26"
    }
)
```

---

## 🎯 FASE 3: Modificación del Flujo de Aprobaciones

### Cambios en `modules/aprobacion_pedidos/logic.py`

#### 3.1 Función `confirmar_fi()` - MODIFICAR

**Antes:**
```python
def confirmar_fi(fi_id: int) -> tuple[bool, str]:
    # Solo cambia estado RESERVADA → CONFIRMADA
    ...
```

**Después:**
```python
def confirmar_fi(fi_id: int, enviar_email: bool = True) -> tuple[bool, str]:
    """
    APROBAR: RESERVADA → CONFIRMADA + Generación PDF + Email
    """
    try:
        with engine.begin() as conn:
            # 1. Cambiar estado
            result = conn.execute(sqlt("""
                UPDATE factura_interna
                SET estado = 'CONFIRMADA'
                WHERE id = :id AND estado = 'RESERVADA'
                RETURNING id, nro_factura, pp_id, cliente_id, vendedor_id
            """), {"id": fi_id})
            
            if result.rowcount == 0:
                return False, "FI no encontrada o ya no está RESERVADA."
            
            fi_data = result.fetchone()
            
        # 2. Log de auditoría
        log_flujo(...)
        
        # 3. Verificar si TODAS las FIs del pedido están confirmadas
        pedido_id = _get_pedido_id_from_fi(fi_id)
        todas_confirmadas = _verificar_todas_fis_confirmadas(pedido_id)
        
        if todas_confirmadas:
            # 4. Cambiar pedido de PENDIENTE → CONFIRMADO
            _confirmar_pedido_web(pedido_id)
            
            # 5. Generar PDF multi-factura
            if enviar_email:
                from core.pdf_factura_interna import FacturaInternaPDF
                from core.email_service import EmailService
                
                # Obtener todas las FIs del pedido
                facturas_data = _get_facturas_para_pdf(pedido_id)
                metadata = _get_metadata_pedido(pedido_id)
                
                # Generar PDF
                pdf_bytes = FacturaInternaPDF.generate(
                    pedido_id=pedido_id,
                    facturas=facturas_data,
                    metadata=metadata
                )
                
                # 6. Enviar email
                destinatarios = _get_email_destinatarios(
                    cliente_id=fi_data['cliente_id'],
                    vendedor_id=fi_data['vendedor_id']
                )
                
                EmailService.send_from_template(
                    template="factura_confirmada",
                    to=destinatarios,
                    context=metadata,
                    attachments=[{
                        "filename": f"FI-{metadata['nro_pedido']}.pdf",
                        "content": pdf_bytes
                    }]
                )
        
        return True, "FI confirmada exitosamente."
        
    except Exception as e:
        DBInspector.log(f"[FI] Error confirmando {fi_id}: {e}", "ERROR")
        return False, str(e)
```

#### 3.2 Nuevas funciones auxiliares

```python
def _get_pedido_id_from_fi(fi_id: int) -> int | None:
    """Obtiene el pedido_venta_rimec.id desde una FI"""
    ...

def _verificar_todas_fis_confirmadas(pedido_id: int) -> bool:
    """Verifica si TODAS las FIs de un pedido están CONFIRMADAS"""
    ...

def _confirmar_pedido_web(pedido_id: int):
    """Cambia estado de pedido_venta_rimec: PENDIENTE → CONFIRMADO"""
    ...

def _get_facturas_para_pdf(pedido_id: int) -> list[dict]:
    """Obtiene datos de todas las FIs de un pedido para el PDF"""
    ...

def _get_metadata_pedido(pedido_id: int) -> dict:
    """Obtiene metadatos del pedido (cliente, vendedor, etc.)"""
    ...

def _get_email_destinatarios(cliente_id: int, vendedor_id: int) -> list[str]:
    """Obtiene emails del vendedor y supervisor"""
    ...
```

---

## 🎯 FASE 4: Actualización de Estados

### 4.1 Tabla `pedido_venta_rimec` - ESTADOS

**Actual:**
- `PENDIENTE` → Esperando aprobación

**Nuevo:**
- `PENDIENTE` → Recibido desde RIMEC WEB (sin revisar)
- `RESERVADO` → Al menos 1 FI creada (equivalente a RESERVADA en FI)
- `CONFIRMADO` → Todas las FIs confirmadas + Email enviado
- `AUTORIZADO` → [Mantener para compatibilidad]
- `RECHAZADO` → Rechazado completamente

### 4.2 Migración para nuevos estados

```sql
-- MIG-095: Sincronización de estados PVR con FI
BEGIN;

-- Agregar estado RESERVADO si no existe
ALTER TABLE pedido_venta_rimec 
    DROP CONSTRAINT IF EXISTS pedido_venta_rimec_estado_check;

ALTER TABLE pedido_venta_rimec 
    ADD CONSTRAINT pedido_venta_rimec_estado_check 
    CHECK (estado IN ('PENDIENTE', 'RESERVADO', 'CONFIRMADO', 'AUTORIZADO', 'RECHAZADO'));

-- Actualizar pedidos existentes con FIs RESERVADAS
UPDATE pedido_venta_rimec pvr
SET estado = 'RESERVADO'
WHERE estado = 'PENDIENTE'
  AND EXISTS (
      SELECT 1 FROM factura_interna fi
      WHERE fi.pedido_id = pvr.id
        AND fi.estado = 'RESERVADA'
  );

COMMIT;
```

---

## 🎯 FASE 5: Configuración de Email

### 5.1 Variables de entorno (`.env`)

```bash
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@rimec.com.py
SMTP_PASS=tu_password_aqui
SMTP_FROM_NAME=RIMEC Business Intelligence
```

### 5.2 Plantillas HTML (`templates/email/`)

**Archivo:** `templates/email/factura_confirmada.html`

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; }
        .container { max-width: 600px; margin: 0 auto; }
        .header { background: #1e3a8a; color: white; padding: 20px; }
        .content { padding: 20px; }
        .footer { background: #f3f4f6; padding: 15px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Factura Interna Confirmada</h2>
        </div>
        <div class="content">
            <p>Estimado/a <strong>{{vendedor_nombre}}</strong>,</p>
            
            <p>Se ha confirmado la factura interna del pedido:</p>
            
            <ul>
                <li><strong>Nro. Pedido:</strong> {{nro_pedido}}</li>
                <li><strong>Cliente:</strong> {{cliente_nombre}}</li>
                <li><strong>Total Pares:</strong> {{total_pares}}</li>
                <li><strong>Total Neto:</strong> {{total_monto}}</li>
            </ul>
            
            <p>Encontrarás el detalle completo en el archivo PDF adjunto.</p>
            
            <p><strong>Facturas generadas:</strong></p>
            <ul>
                {% for fi in facturas %}
                <li>{{fi.nro_factura}} - {{fi.marca}} ({{fi.total_pares}} pares)</li>
                {% endfor %}
            </ul>
        </div>
        <div class="footer">
            <p>RIMEC Business Intelligence · Nexus Core</p>
            <p style="font-size: 12px; color: #6b7280;">
                Este es un correo automático. Por favor no responder.
            </p>
        </div>
    </div>
</body>
</html>
```

---

## 📅 CRONOGRAMA DE IMPLEMENTACIÓN

### Sprint 1 (2-3 días)
- [x] ✅ Análisis y diseño (completado)
- [ ] 📝 Crear `core/email_service.py`
- [ ] 🧪 Tests de envío de email
- [ ] 📄 Plantillas HTML básicas

### Sprint 2 (3-4 días)
- [ ] 🎨 Crear `core/pdf_factura_interna.py`
- [ ] 📊 Integrar con ReportEngine
- [ ] 🖼️ Manejo de imágenes (miniaturas)
- [ ] 🧪 Tests de generación PDF

### Sprint 3 (2-3 días)
- [ ] 🔄 Modificar `confirmar_fi()` en logic.py
- [ ] 📝 Crear funciones auxiliares
- [ ] 🗃️ Migración MIG-095 (estados)
- [ ] 🧪 Tests de integración

### Sprint 4 (1-2 días)
- [ ] 🎯 UI: Feedback visual de confirmación
- [ ] ✉️ Logs de emails enviados
- [ ] 📱 Notificaciones en UI
- [ ] 🧪 Tests end-to-end

### Sprint 5 (1 día)
- [ ] 🐛 Bug fixes y refinamiento
- [ ] 📖 Documentación
- [ ] 🚀 Deploy a producción

---

## 🔧 DEPENDENCIAS TÉCNICAS

### Python Packages (agregar a `requirements.txt`)

```txt
# Email
Jinja2==3.1.3          # Plantillas HTML
python-dotenv==1.0.0   # Variables de entorno

# PDF (ya instalado)
reportlab==4.0.7       # Generación PDF
Pillow==10.1.0         # Manejo de imágenes
```

### Estructura de directorios

```
control_central/
├── templates/
│   └── email/
│       ├── factura_confirmada.html
│       └── base.html
│
├── logs/
│   └── emails/
│       └── YYYY-MM-DD.log
│
└── static/
    └── img/
        └── logo_rimec.png
```

---

## 🎯 CRITERIOS DE ACEPTACIÓN

### ✅ Funcionalidad Core
- [ ] Email se envía correctamente con PDF adjunto
- [ ] PDF contiene todas las facturas del pedido
- [ ] Miniaturas de productos se muestran correctamente
- [ ] Descuentos se calculan y muestran correctamente
- [ ] Estados se actualizan en orden correcto

### ✅ Robustez
- [ ] Sistema funciona aunque falle el envío de email
- [ ] Logs de auditoría completos
- [ ] Rollback automático en caso de error
- [ ] Retry mechanism para emails fallidos

### ✅ Experiencia de Usuario
- [ ] Feedback visual inmediato al confirmar
- [ ] Email llega en menos de 30 segundos
- [ ] PDF es legible y profesional
- [ ] Botones Confirmar/Anular bien diferenciados

---

## 📝 NOTAS IMPORTANTES

1. **Email agnóstico:** El EmailService debe poder cambiarse a SendGrid, AWS SES, etc. sin tocar código de negocio

2. **PDF reutilizable:** FacturaInternaPDF debe poder usarse para otros tipos de facturas/reportes

3. **Estados sincronizados:** PVR.estado debe reflejar el estado real de las FIs

4. **Rollback seguro:** Si falla el email, la FI queda confirmada igual (email es informativo)

5. **Auditoría completa:** Registrar TODOS los eventos (confirmación, email enviado, errores)

---

## 🚀 PRÓXIMOS PASOS

1. **Revisar y aprobar** este plan
2. **Crear issues/tasks** en el sistema de seguimiento
3. **Iniciar Sprint 1** con EmailService
4. **Reunión de seguimiento** al final de cada sprint

---

**Fecha:** 2026-05-26  
**Autor:** Claude Sonnet 4.5 + Héctor  
**Versión:** 1.0
