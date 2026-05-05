# Módulo: Inteligencia de Ventas
> Leer antes de modificar cualquier archivo de este módulo.

## Qué hace
Analiza ventas 2025 vs 2026 con objetivo configurable por el usuario.
Segmenta cartera de clientes, ranking de marcas y gestión de vendedores.
Genera PDFs ejecutivos estilo IMF. Conecta a `v_ventas_pivot` en Supabase.

## Archivos
| Archivo | Responsabilidad |
|---|---|
| `__init__.py` | MODULE_INFO — registro en el Registry |
| `sidebar.py` | Controles de filtros — solo actualiza draft, nunca ejecuta SQL |
| `ui.py` | 4 tabs: Dashboard / Clientes / Marcas / Vendedores |
| `logic.py` | Distribuidor puro — groupby + _path para treeData. Sin matemáticas. |
| `export.py` | Puente → ReportEngine (PDF) |
| `styles_sales_report.py` | Piano Geometry JS, value formatters AgGrid |

## Fuente de datos
**Vista:** `v_ventas_pivot` en Supabase
**Columnas clave:** `tipo, marca, cliente, codigo_cliente, vendedor, cadena,
mes_idx, id_categoria, categoria, monto_26, monto_25, cant_26, cant_25`
**Matemáticas en BD:** pivot 2025/2026 ya hecho en la vista
**Matemáticas en Python:** solo `objetivo_pct` (parámetro runtime del usuario)

## Contrato logic → ui (NO romper)
```python
{
  'evolucion':  DataFrame,          # Semestre, Mes, ALIAS_TARGET, ALIAS_CURRENT, ALIAS_VAR
  'cartera': {
      'crecimiento':   DataFrame,   # variación >= 0, con _path
      'decrecimiento': DataFrame,   # variación < 0, con _path
      'sin_compra':    DataFrame,   # real=0, obj>0, con _path
  },
  'marcas':    (df_ranking, df_detalle),
  'vendedores': (df_ranking, df_detalle),
  'kpis': {'clientes_26': int, 'atendimiento': float, 'variacion_total': float},
}
```

## Constantes críticas (de core/constants.py)
```python
ALIAS_CURRENT_VALUE = "Monto 26"
ALIAS_TARGET_VALUE  = "Monto Obj"
ALIAS_VARIATION     = "Variación %"
MES_MAP / MES_NOMBRES / MESES_LISTA  # NO redefinir aquí
```

## Reglas de negocio
- Variación cuando obj=0 y real>0 → `NaN` interno → `∞` en pantalla y PDF
- Separador treeData: `|||`  Ej: `"CADENA|||CLIENTE|||MARCA"`
- Default arranque: Calzados + Programado (id=3) + 1er semestre
- Botones semestre → solo draft. EJECUTAR ORDEN → SQL.

## Estado actual: ✅ Estable
- Filtros operativos: departamento, categoría, meses, marcas, cadenas,
  vendedores, clientes, código cliente exacto
- Export PDF individual y batch ZIP por marca/vendedor
- ∞ en variación sin base: operativo en AgGrid y PDF
- Columnas texto ocultas en treeData (ya representadas en jerarquía)

## Deuda técnica conocida
- `render_fragmented_grid()` en ui.py: 140+ líneas, candidata a refactor futuro
- `get_full_analysis_package()` en logic.py: 200+ líneas, misma situación
- Sin tests unitarios automáticos
