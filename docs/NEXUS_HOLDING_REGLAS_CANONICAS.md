# Nexus Holding — Reglas Canónicas

Políticas y reglas de negocio fundamentales del ecosistema Nexus.

---

## 1. Política de Clientes — Tránsito y Canales de Venta

### 1.1 Universo de Clientes RIMEC

**Mercadería en Tránsito / Compra Previa**:
- Pertenece al universo general de clientes **RIMEC**
- NO es exclusiva de un único cliente
- Disponible para venta a cualquier cliente autorizado RIMEC

### 1.2 Cliente 5000 — Bazar Web Virtual EXCLUSIVO

**Identificación**:
- `cliente_v2.id_cliente = 5000`
- Nombre: (verificar en base de datos)

**Función**:
- **Único cliente autorizado** para alimentar **Bazar Web** (tienda virtual)
- Flujo: Compra Web → Depósito Web → Bazar Web página

**Restricción**:
- Solo mercadería asignada/vendida a cliente 5000 aparece en catálogo web público
- Otros clientes RIMEC NO alimentan la tienda virtual

### 1.3 Clientes Físicos Bazzar (Tiendas Físicas)

**Clientes**:
- `2100` — Fernando Adultos
- `2900` — Fernando Niños
- `2400` — San Martin Adultos
- `2700` — San Martin Niños
- `3100` — Palma Adultos
- `3200` — Palma Niños

**Características**:
- Clientes **RIMEC** (no Bazar Web)
- Representan tiendas físicas de la red Bazzar
- **NO alimentan** la tienda virtual
- Futuro: módulo de logística / confirmación de entregas

**Restricción**:
- Mercadería asignada a estos clientes NO debe aparecer en catálogo web
- Son clientes internos para gestión de stock físico

### 1.4 Implementación Técnica

**Obligatorio**:
- Todo flujo que alimente **Bazar Web** debe filtrar `WHERE cliente_id = 5000`
- Vistas de stock web (`v_stock_web`) deben excluir otros clientes
- Movimientos a `ALM_WEB_01` deben validar cliente 5000

**Verificar**:
- `modules/compra_web/`
- `modules/deposito_web/`
- `modules/pedido_web/`
- Vistas relacionadas a stock web

---

## 2. (Espacio para otras reglas canónicas)

---

**Documento**: NEXUS_HOLDING_REGLAS_CANONICAS.md  
**Última actualización**: 2026-06-01  
**OR**: OR-NEXUS-POLITICA-CLIENTE-5000-BAZAR-WEB-001
