# OT-NEXUS-BAZAR-WEB-CLIENTE-5000-GUARD-002

**Tipo**: Guardia / Validación  
**Prioridad**: MEDIA (preventivo)  
**Estado**: PROPUESTA  
**OR**: OR-NEXUS-POLITICA-CLIENTE-5000-BAZAR-WEB-001

---

## Objetivo

Implementar validación técnica para garantizar que **solo Cliente 5000** pueda alimentar Bazar Web virtual.

---

## Contexto

### Política de negocio (OR-001)

- Mercadería en tránsito pertenece al universo RIMEC (no exclusiva de 5000)
- **Solo cliente 5000** debe alimentar Bazar Web (tienda virtual pública)
- Clientes físicos Bazzar (2100, 2900, 2400, 2700, 3100, 3200) NO alimentan web

### Análisis de código (realizado 2026-06-01)

**Flujo actual**:
1. FAC-INT creada en Facturación (`modules/facturacion/ui.py`)
   - UI sugiere cliente 5000 como default (`value="5000"`)
   - Campo es **editable** (sin validación)
2. Botón "ENVIAR A WEB BAZAR" (`modules/facturacion/logic.py:enviar_factura_a_web_bazar`)
   - Llama `crear_traspaso_por_factura` (compra_legal/logic.py:163)
   - **NO valida cliente**
3. Compra Web confirma recepción (`modules/compra_web/ui.py`)
   - Llama `procesar_ingreso_bazar` (compra_legal/logic.py:1410)
   - Crea movimiento INGRESO_COMPRA → ALM_WEB_01
   - **NO valida cliente**
4. Vista `v_stock_web` (bazzar-web/supabase/v_stock_web.sql)
   - Filtra por almacén (ALM_WEB_01), NO por cliente
   - Stock disponible para catálogo público

**Riesgo identificado**:
- Un operador podría cambiar cliente en UI Facturación
- FAC-INT con cliente != 5000 podría enviarse a Web Bazar
- Stock de clientes físicos (2100-3200) aparecería en catálogo público

---

## Tareas

### Opción A: Validación en UI (sugerida)

**Archivo**: `modules/facturacion/ui.py`

**Cambio**:
```python
# Línea 225-230: Hacer campo cliente readonly para FAC-INT Bazar Web
if es_carga_manual_web:
    st.markdown("**Cliente destino:** 5000 (Bazar Web — exclusivo)")
    cod_cliente = "5000"  # No editable
else:
    cod_cliente = st.text_input(
        "Código Cliente (destino)",
        value="5000",
        key="fac_carga_cliente",
    )
```

### Opción B: Validación en Backend (más robusta)

**Archivo**: `modules/facturacion/logic.py`

**Función**: `enviar_factura_a_web_bazar` (línea ~170)

**Cambio**:
```python
def enviar_factura_a_web_bazar(numero_factura: str) -> tuple[bool, str]:
    try:
        with engine.begin() as conn:
            # ═══ GUARDIA CLIENTE 5000 ═══════════════════════════════════════
            fi = conn.execute(sqlt("""
                SELECT cliente_id FROM factura_interna WHERE nro_factura = :nro
            """), {"nro": numero_factura}).fetchone()
            
            if fi and int(fi[0]) != 5000:
                return False, (
                    f"FAC-INT debe ser Cliente 5000 para enviar a Bazar Web. "
                    f"Cliente actual: {fi[0]}"
                )
            # ════════════════════════════════════════════════════════════════
            
            # ... resto del código
```

**O en**: `crear_traspaso_por_factura` (compra_legal/logic.py:163)

```python
def crear_traspaso_por_factura(
    conn, id_pp, id_marca, numero_factura, items_tallas
) -> int:
    # ═══ GUARDIA CLIENTE 5000 ═══════════════════════════════════════
    fi = conn.execute(sqlt("""
        SELECT cliente_id FROM factura_interna WHERE nro_factura = :nro
    """), {"nro": numero_factura}).fetchone()
    
    if fi and int(fi[0]) != 5000:
        raise ValueError(
            f"Solo Cliente 5000 puede alimentar Bazar Web. "
            f"FAC-INT {numero_factura} tiene cliente {fi[0]}"
        )
    # ════════════════════════════════════════════════════════════════
    
    # ... resto del código
```

### Opción C: Validación en Vista (menos flexible)

**Archivo**: `bazzar-web/supabase/v_stock_web.sql`

**Cambio**: NO RECOMENDADO
- Vista v_stock_web no tiene acceso directo a cliente
- Requeriría JOIN adicional con factura_interna (impacto performance)
- Mejor validar en el flujo de ingreso

---

## Recomendación

**Implementar Opción B (Backend)** en `enviar_factura_a_web_bazar`:
- Validación robusta (no bypasseable desde UI)
- Mensaje claro al operador
- Sin impacto en performance (solo al enviar)
- Protege contra errores humanos y futuros cambios en UI

**Complementar con Opción A (UI)**:
- Hacer campo readonly en Carga Manual Web
- Feedback visual (usuario ve que 5000 es obligatorio)
- Mejor UX (error previo al intento)

---

## Archivos a modificar

| Archivo | Función | Cambio |
|---------|---------|--------|
| modules/facturacion/logic.py | `enviar_factura_a_web_bazar` (línea ~170) | Validar cliente_id = 5000 antes de crear traspaso |
| modules/facturacion/ui.py | Carga Manual Web (línea 225-230) | Campo cliente readonly = "5000" |

---

## Testing

1. **Caso positivo**: FAC-INT cliente 5000 → ENVIAR A WEB BAZAR → OK
2. **Caso negativo**: FAC-INT cliente 2100 → ENVIAR A WEB BAZAR → Error claro
3. **Caso UI**: Carga Manual Web → campo cliente no editable
4. **Caso regresión**: FAC-INT existentes cliente != 5000 → no afectadas (solo nuevos envíos)

---

## Rollback

Si se detecta problema:
- Remover validación de `enviar_factura_a_web_bazar`
- Restaurar campo editable en UI
- Sin impacto en datos (solo lógica de validación)

---

## Fecha propuesta

2026-06-01

**Estimación**: 1 hora (validación + testing)

**Riesgo**: BAJO (solo agrega validación, no modifica flujo existente)
