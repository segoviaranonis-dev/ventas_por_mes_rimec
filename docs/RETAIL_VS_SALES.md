# Dos fuentes Excel, dos tablas

| Módulo | Excel | Tabla Supabase |
|--------|-------|----------------|
| **Sales Report** | Ventas agregadas (cliente, marca, monto, …) | `registro_ventas_general_v2` |
| **Retail** | VTA SM — **solo hoja `st+vt+RC`** | `registro_st_vt_rc_reposicion` |

Pilares (`linea`, `referencia`, `material`, `color`): solo para **filtros e imágenes** en Retail.

Import Retail: Nexus → **Retail (st+vt+RC)**. Migración: `060_registro_st_vt_rc_reposicion.sql`.

**Política de import:** cada Excel nuevo hace `DELETE` de toda la tabla y luego inserta solo ese archivo (reemplazo total).
