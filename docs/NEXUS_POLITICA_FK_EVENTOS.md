# Nexus Holding — Politica FK/Eventos

> Rol: documento canonico de arquitectura de datos.  
> Vigencia: inmediata.  
> Principio: Nexus no procesa Excel como verdad; Nexus transforma datos externos en FKs y registra eventos combinatorios.

---

## 1. Ley principal

Todo dato externo que entra al holding debe pasar por pilares antes de alimentar filtros, reportes, catalogos, precios, stock u operaciones.

```txt
Excel / CSV / Proforma / Reporte externo
→ parseo inicial
→ busqueda o alta controlada en pilares
→ obtencion de FKs
→ eventos internos
→ reportes / catalogos / operaciones
```

Despues de cruzar esa frontera, el sistema no debe razonar con el texto original del Excel como fuente de verdad.

---

## 2. Los pilares son la aduana

Pilares base:

| Pilar | FK canonica | Codigo proveedor |
|---|---|---|
| Linea | `linea_id` | `linea.codigo_proveedor` |
| Referencia | `referencia_id` | `referencia.codigo_proveedor` |
| Material | `material_id` | `material.codigo_proveedor` |
| Color | `color_id` | `color.codigo_proveedor` |
| Grada / talla | `talla_id` o `grades_json` canonico | curva / talla |

Regla:

```txt
Descripciones son presentacion.
FKs son logica.
```

---

## 3. Headers y filtros

Todo header, filtro o agrupador de UI debe salir de FKs o maestras relacionadas:

| UI | Fuente correcta |
|---|---|
| Marca | `linea.marca_id` → `marca_v2` |
| Genero | `linea.genero_id` → `genero` |
| Estilo | `linea_referencia.grupo_estilo_id` → `grupo_estilo_v2` |
| Tipo 1 | `linea_referencia.tipo_1_id` → `tipo_1` |
| Color | `color_id` → `color` |
| Material | `material_id` → `material` |
| Llegada | `quincena_arribo_id` → `quincena_arribo` |

Prohibido en codigo nuevo:

- filtrar por descripcion si existe FK;
- unir tablas por texto humano;
- crear headers desde strings sueltos de Excel;
- usar `linea.caso_id` como caso comercial nuevo.

---

## 4. Eventos combinatorios

Nexus registra eventos de combinaciones de FKs.

```txt
Evento = combinacion de FKs + contexto + tiempo + operacion
```

Ejemplos:

| Evento | FKs / contexto que debe preservar |
|---|---|
| `precio_evento` | proveedor, linea, referencia, material, caso, lista |
| `pedido_proveedor` | PP, linea, referencia, material, color, grada, proveedor, llegada |
| `factura_interna` | FI, cliente, vendedor, PP, lista, caso, categoria, snapshot molecular |
| `compra_legal` | CL, PP, categoria, precio_evento, usuario, timestamp |
| `movimiento` | almacen, combinacion_id, cantidad, tipo movimiento |
| `pedido_web` | cliente_web, combinacion_id, precio, reserva |
| `retail batch` | lote, tienda/origen, molecula, venta, stock, fecha |

Los pilares son identidad. Los eventos son historia.

---

## 5. Report, RIMEC Web y Bazzar

### Report

- Sales Report usa `registro_ventas_general_v2` y maestras `_v2`.
- Ventas con Fotos puede parsear `imagen` como molecula L-R-M-C para cruzar contra pilares.
- Retail procesa Excel Bazzar y debe normalizar contra pilares.

### RIMEC Web

- Catalogo y Estadisticas no pueden contradecirse.
- Si Estadisticas suma PP por pilares, Catalogo debe poder explicar cualquier diferencia.
- Filtros del catalogo deben nacer de pilares/FKs.

### Bazzar Web

- Solo `cliente_id = 5000` alimenta tienda virtual.
- Tiendas fisicas Bazzar son clientes RIMEC, pero pertenecen a futuro modulo logistico.
- Stock web debe anclarse a `combinacion_id`.

---

## 6. Regla de auditoria

Si un modulo muestra datos distintos para el mismo PP, SKU, cliente o evento:

1. identificar fuente de cada pantalla;
2. comparar FKs;
3. localizar etapa donde se pierde o duplica informacion;
4. corregir arquitectura, no solo UI;
5. documentar con evidencia.

---

## 7. Frase canonica

> Nexus no procesa Excel. Nexus transforma Excel en FKs y registra eventos combinatorios auditables.
