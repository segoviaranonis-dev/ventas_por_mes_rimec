# Auditoria de flujo FK/Eventos — Nexus Core → RIMEC Web → Bazzar Web

> Rol: auditoria de arquitectura e integridad.  
> Fecha: 2026-06-01.  
> Estado: canonico para remediacion; no es historico.  
> Regla base: ver `NEXUS_POLITICA_FK_EVENTOS.md`.

---

## 1. Resumen ejecutivo

El ecosistema ya tiene la arquitectura correcta en varias zonas: FI con snapshot, traspaso con `combinacion_id`, deposito web y Bazzar Web usando stock por combinacion. Pero aun hay zonas donde el sistema viejo o consultas de presentacion rompen la filosofia FK-first.

Riesgo central:

```txt
Una pantalla puede mostrar una verdad distinta a otra porque no comparten la misma fuente normalizada por pilares.
```

Caso testigo:

```txt
PP-2026-0012
Estadisticas: 9.904 pares
Catalogo: 8.340 pares
```

Este tipo de divergencia no es aceptable en produccion porque puede ocultar mercaderia vendible o generar decisiones equivocadas.

---

## 2. Mapa del flujo

```txt
Excel / Proforma / CSV
→ parseo
→ pilares
→ FKs
→ eventos
→ vistas / APIs
→ UI / PDF / catalogo
```

Flujo operativo:

```txt
Motor de precios
→ Intencion de Compra
→ Pedido Proveedor
→ Factura Interna
→ Compra Legal
→ Facturacion
→ Deposito RIMEC
→ Compra Web
→ Deposito Web
→ Bazzar Web
```

Flujo comercial web:

```txt
PP / FI / deposito
→ v_stock_rimec
→ RIMEC Web catalogo
→ carrito vendedor
→ FI / pedido
```

Flujo Bazzar:

```txt
movimiento_detalle + combinacion_id
→ v_stock_web
→ Bazzar Web catalogo
→ checkout
→ pedido_web
```

---

## 3. Donde el sistema esta fuerte

| Area | Fortaleza | Riesgo mitigado |
|---|---|---|
| FI card | `core/fi_card.py` como vista canonica | Vistas de FI divergentes |
| Compra Legal | sello auditable PP → CL | perdida de quien/cuando/precio/categoria |
| Deposito RIMEC | vendido desde FI activas | contradiccion con Facturacion |
| Bazzar Web | `combinacion_id` en detalle | venta por producto equivocado |
| Motor de precios | `precio_evento` y `precio_lista` | caso comercial fuera de evento |
| Retail | prevalidacion Excel contra pilares | Excel viejo rompe import |

---

## 4. Desviaciones detectadas

### 4.1 Pedido Proveedor todavia mezcla texto y FK

`pedido_proveedor_detalle` conserva linea/referencia como texto/codigo en varias rutas. Eso es aceptable como transicion, pero no debe ser fuente final.

Riesgo:

```txt
dos filas con mismo texto pueden mapear distinto si faltan FKs o proveedor.
```

Accion:

```txt
Agregar/usar linea_id y referencia_id en PPD de forma canonica.
```

### 4.2 Caso comercial legacy

Todo caso comercial nuevo debe vivir en:

```txt
precio_evento
precio_evento_caso
precio_lista
factura_interna.lista_precio_id / caso
```

No en:

```txt
linea.caso_id
```

Accion:

```txt
Eliminar dependencias nuevas de linea.caso_id y dejarlo solo como legacy.
```

### 4.3 Catalogo RIMEC Web vs Estadisticas

Estadisticas agrupa desde fuente directa y normalizacion molecular.

Catalogo usa:

```txt
v_stock_rimec
filtros.ts
atributosLinea.ts
agruparTarjetasCatalogo.ts
```

Riesgos detectados:

- limite default Supabase 1.000 filas;
- query principal y query de filtros deben tener `.range()`;
- `totalPares` puede usar cantidad inicial en vez de saldo disponible;
- filtros pueden usar strings en color;
- cache puede ocultar fix en produccion;
- catalogo y estadisticas no comparten contrato de reconciliacion.

Accion:

```txt
Crear prueba de reconciliacion por PP: Estadisticas vs Catalogo.
```

### 4.4 Retail Bazzar y Excel viejo

Retail es primer puente RIMEC ↔ Bazzares. No debe bloquear por datos incompletos del sistema viejo.

Regla:

```txt
Material/color sin descripcion pueden entrar como pendiente o sentinela.
Linea/referencia deben resolverse o insertarse con protocolo.
Grada no identificada queda auditada.
```

Riesgo:

```txt
si Report muestra conteos inflados por JOIN, direccion pierde confianza.
```

Accion:

```txt
Evitar joins por OR id/codigo. Usar FK o codigo_proveedor deterministico.
```

### 4.5 Bazzar Web

Riesgos actuales:

- API legacy de checkout si sigue expuesta;
- confirmacion publica por ID puede exponer pedidos;
- imagenes pueden fallar si no se usa misma convencion Storage;
- precio debe venir de BD, nunca del cliente;
- stock debe reservarse transaccionalmente.

Accion:

```txt
Auditoria Bazzar Web antes de considerarlo e-commerce real.
```

---

## 5. Riesgos priorizados

| Severidad | Riesgo | Impacto |
|---|---|---|
| CRITICO | Catalogo oculta pares disponibles | perdida de venta, falsos negativos |
| CRITICO | Bazzar Web permite precio/stock manipulable | fraude o perdida economica |
| ALTO | PP/CL sin snapshot completo | imposibilidad de auditoria futura |
| ALTO | PPD sin FK L/R canonica | errores de molecula |
| ALTO | Imagen no resuelta en Bazzar Web | perdida de confianza comercial |
| MEDIO | Retail JOIN duplica filas | reportes inflados |
| MEDIO | Color por string en filtros | filtros falsos |
| MEDIO | Cache Vercel oculta datos vivos | decisiones con datos viejos |

---

## 6. OTs prioritarias

### OT 1 — Reconciliacion catalogo/estadisticas RIMEC Web

Objetivo:

```txt
Para cada PP, comparar pares de Estadisticas vs Catalogo y fallar si difieren sin explicacion.
```

### OT 2 — Vista normalizada unica para catalogo

Objetivo:

```txt
Crear `v_catalogo_rimec_normalizado` o endpoint que use la misma normalizacion molecular que Estadisticas.
```

### OT 3 — FK canonica en Pedido Proveedor Detalle

Objetivo:

```txt
Persistir `linea_id` y `referencia_id` en PPD y migrar rutas que aun dependen de texto.
```

### OT 4 — Guard cliente 5000 para Bazzar Web virtual

Objetivo:

```txt
Solo cliente 5000 puede alimentar Compra Web / Deposito Web / Bazzar Web.
```

### OT 5 — Auditoria Bazzar Web ecommerce real

Objetivo:

```txt
Cerrar API legacy, proteger pedido publico, validar stock/precio/imagen.
```

### OT 6 — Report Retail ranking comercial

Objetivo:

```txt
Ranking por `IMAGEN` + `TIPO=VENTA` + cantidad desc, top 30/100/500/1000.
```

---

## 7. Politica de no intervencion

Hasta que esta auditoria sea convertida en OTs específicas:

```txt
YAMBAI no debe modificar arquitectura de flujo FK/eventos sin OT.
MARTA no debe modificar reportes/catálogos fuera de su OT.
MARTA2 no debe implementar paridad parcial si la ancla es Streamlit.
```

Los albañiles pueden:

- diagnosticar;
- ejecutar OT acotada;
- aportar evidencia.

No pueden:

- redefinir fuente de verdad;
- cambiar filtros de negocio sin aprobacion;
- crear bypass de pilares;
- corregir con texto lo que debe resolverse con FK.

---

## 8. Criterio de cierre de la auditoria

Esta auditoria se considera operacionalizada cuando existan:

1. prueba de reconciliacion catalogo/estadisticas;
2. contrato documentado para `v_stock_rimec` o vista nueva;
3. Bazzar Web auditado como e-commerce real;
4. Retail sin conteos inflados;
5. PP/FI/CL con snapshots auditables;
6. cliente 5000 blindado para Bazzar Web virtual.

---

## 9. Frase final

La precision milimetrica no es estetica. Es defensa legal, comercial y contable.
