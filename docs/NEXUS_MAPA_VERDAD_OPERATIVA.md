# Nexus Core — Mapa de Verdad Operativa

## Ley principal

**Frontend muestra. Backend valida. Base de datos conserva la verdad.**

Ninguna pantalla debe inventar stock, saldo, vendido, precio, caso o estado. Si un dato se ve en UI, debe venir de una fuente oficial: tabla, vista, RPC o funcion transaccional.

## Flujo critico PP -> Bazzar

```text
pedido_proveedor
  -> pedido_proveedor_detalle
  -> factura_interna
  -> factura_interna_detalle
  -> compra_legal / compra_legal_pedido
  -> traspaso
  -> traspaso_detalle
  -> movimiento
  -> movimiento_detalle
  -> v_stock_web / v_stock_rimec
  -> Bazzar Web / RIMEC Web / Report
```

## Fuentes oficiales por dato

| Dato | Fuente oficial | Prohibido |
|---|---|---|
| Pares iniciales PP | `pedido_proveedor_detalle.cantidad_pares` | recalcular en UI desde Excel |
| Cajas iniciales PP | `pedido_proveedor_detalle.cantidad_cajas` | inferir por texto |
| Curva base de caja | `pedido_proveedor_detalle.grades_json` | parsear de UI como verdad final |
| Pares facturados FI | `factura_interna_detalle.pares` | asumir que equivale a una caja |
| Cajas facturadas FI | `factura_interna_detalle.cajas` | recalcular por cantidad de tallas |
| Vendido / bloqueado PP | `pedido_proveedor_detalle.pares_vendidos` y legacy `venta_transito` solo como compatibilidad | contar desde una sola pantalla |
| Saldo PP | vista/RPC basada en `cantidad_pares - vendido` | calcular distinto por modulo |
| Traspaso al web | `traspaso_detalle.cantidad` | copiar `grades_json` sin escalar a FI |
| Ingreso real stock web | `movimiento_detalle` con `movimiento.estado='CONFIRMADO'` | tocar `v_stock_web` directo |
| Stock Bazzar | `v_stock_web` | calcular en React/localStorage |
| Precio web | vista/RPC oficial de precio | aceptar precio del navegador |
| Imagen producto | protocolo `docs/NEXUS_PROTOCOLO_IMAGENES_PRODUCTO.md` | usar IDs internos para nombre de archivo |

## Reglas de rigidez

1. Las pantallas no calculan verdad comercial; solo consumen fuentes oficiales.
2. Si dos pantallas muestran el mismo dato, ambas deben leer la misma vista/RPC o la misma consulta compartida.
3. Toda escritura que afecta stock o dinero debe estar en una transaccion.
4. Una FI confirmada no puede generar un traspaso parcial salvo regla de negocio documentada.
5. `grades_json` representa curva base; antes de viajar a traspaso debe escalarse a `factura_interna_detalle.pares`.
6. Material/color deben resolverse por codigo proveedor/F9 cuando exista; descripcion es fallback, no identidad.
7. Bazzar no decide stock; Bazzar lee `v_stock_web`.
8. Report no decide stock; Report informa.

## Auditoria obligatoria antes de pasar PPs a Compra

Antes de promover PPs a Compra Legal o confirmar ingreso web, correr:

```bat
python scripts/auditar_verdad_operativa_pp.py --pp PP-2026-0010 --json
```

La auditoria debe probar:

- PP inicial = suma `pedido_proveedor_detalle.cantidad_pares`
- FI = suma `factura_interna_detalle.pares`
- Traspaso = suma `traspaso_detalle.cantidad`
- Movimiento = suma `movimiento_detalle.cantidad * signo`
- Web = suma `v_stock_web.stock_web`
- Material/color de imagen vienen de codigos proveedor/F9

## Semaforo

| Estado | Significado |
|---|---|
| OK | Todas las capas coinciden |
| WARN | Hay diferencia explicable o flujo incompleto |
| BUG | Hay descuadre de cantidad, combinacion o imagen |

## Caso probado

`PP-2026-0010 / 10-PV004 / L2305-R1579` revelo dos bugs:

1. `grades_json` de 12 pares viajaba sin escalar a FI de 36.
2. Material se resolvia por descripcion y elegia otro codigo proveedor, rompiendo imagen.

Fix publicado:

- `modules/compra_legal/grades.py`
- `modules/compra_legal/logic.py`
- `tests/test_compra_legal_grades_scaling.py`
