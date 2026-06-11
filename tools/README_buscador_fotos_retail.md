# Buscador de fotos RETAIL — herramienta auxiliar

## Objetivo

`buscador_de_fotos_retail.py` compara las imágenes referenciadas en:

```txt
registro_st_vt_rc_reposicion
```

contra el bucket público:

```txt
Supabase Storage > productos
```

**Diferencias con buscador_de_fotos.py:**
- Lee de tabla **Retail** (no Sales Report)
- Usa columna **`imagen_nombre`** (no `imagen`)
- **No filtra** por `id_tipo` (no existe en retail)

---

## Qué hace

1. Busca imágenes únicas en `registro_st_vt_rc_reposicion` (columna `imagen_nombre`).
2. Lista archivos existentes en Storage `productos`.
3. Detecta duplicados tipo `(1).jpg`.
4. Calcula faltantes.
5. Pide carpeta origen donde buscar fotos.
6. Pide carpeta respaldo donde copiar las fotos encontradas.
7. Pregunta si querés subirlas a Supabase.
8. Genera CSVs de auditoría.

---

## Cómo ejecutarlo

Desde:

```powershell
cd C:\Users\hecto\Nexus_Core\control_central
```

Ejecutar:

```powershell
python tools\buscador_de_fotos_retail.py
```

Modo diagnóstico sin subir:

```powershell
python tools\buscador_de_fotos_retail.py --dry-run
```

---

## Variables necesarias

Debe encontrar en `.env.local` o variables de entorno:

```txt
NEXT_PUBLIC_SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Si no hay service role, intentará usar anon key, pero para subir normalmente se necesita service role.

---

## Salida

Genera reportes en:

```txt
diagnostico_fotos_retail\YYYYMMDD_HHMMSS\
```

Archivos:

```txt
imagenes_db.csv              - Todas las imágenes en BD (imagen_nombre)
storage_duplicados.csv       - Duplicados tipo "foto (1).jpg" en Storage
faltantes_storage.csv        - Imágenes en BD que NO están en Storage
encontrados_local.csv        - Fotos encontradas en carpeta origen
faltantes_local.csv          - Fotos que NO se encontraron localmente
resultado_upload.csv         - Resultado de subida a Storage (si se ejecutó)
```

---

## Flujo de uso típico

### 1. Diagnóstico inicial

```powershell
python tools\buscador_de_fotos_retail.py --dry-run
```

Esto te muestra:
- Cuántas imágenes hay en BD
- Cuántas ya están en Storage
- Cuántas faltan
- **NO sube nada**, solo diagnóstico

### 2. Buscar y copiar respaldo

```powershell
python tools\buscador_de_fotos_retail.py
```

1. Seleccioná carpeta ORIGEN (donde están las fotos originales)
2. El script busca recursivamente las fotos faltantes
3. Seleccioná carpeta RESPALDO (donde copiar antes de subir)
4. El script copia las fotos encontradas al respaldo

### 3. Subir a Storage

Después de copiar al respaldo, te pregunta:

```
¿Subir X fotos a bucket 'productos'?
```

- **Sí**: Sube las fotos a Supabase Storage
- **No**: Solo queda el respaldo local, no sube nada

---

## Seguridad

- **No borra** duplicados.
- **No borra** fotos existentes.
- **No sobreescribe** fotos en Storage (flag `x-upsert: false`).
- **Primero copia** respaldo local antes de subir.
- **Pide confirmación** antes de subir.

---

## Casos de uso

### Caso 1: Primera población de Storage

```
Situación: Importaste Excel Retail nuevo, tiene 500 imágenes, Storage está vacío.

1. python tools\buscador_de_fotos_retail.py --dry-run
   → Muestra: "500 imágenes en BD, 0 en Storage, 500 faltantes"

2. python tools\buscador_de_fotos_retail.py
   → Seleccionar carpeta con fotos originales
   → Seleccionar carpeta respaldo
   → Confirmar upload
   → Resultado: 500 fotos subidas
```

### Caso 2: Actualización incremental

```
Situación: Storage tiene 400 fotos, nuevo import tiene 50 fotos nuevas.

1. python tools\buscador_de_fotos_retail.py --dry-run
   → Muestra: "450 imágenes en BD, 400 en Storage, 50 faltantes"

2. python tools\buscador_de_fotos_retail.py
   → Busca solo las 50 faltantes
   → Copia a respaldo
   → Sube 50 nuevas
```

### Caso 3: Auditoría sin subir

```
Situación: Querés saber qué fotos faltan pero no subir todavía.

python tools\buscador_de_fotos_retail.py --dry-run

Revisa el CSV:
diagnostico_fotos_retail\20260611_143000\faltantes_storage.csv
```

---

## Diferencias con buscador_de_fotos.py

| Aspecto | Sales (original) | Retail (nuevo) |
|---------|------------------|----------------|
| **Tabla BD** | `registro_ventas_general_v2` | `registro_st_vt_rc_reposicion` |
| **Columna** | `imagen` | `imagen_nombre` |
| **Filtro** | `id_tipo = 1` | Sin filtro (todo Retail) |
| **Uso** | Catálogo ventas | Stock tiendas Bazzar |
| **Bucket** | `productos` | `productos` (mismo) |

---

## Troubleshooting

### Error: "No encuentro SUPABASE_URL"

**Causa:** No hay `.env.local` o variables no definidas.

**Fix:**
```powershell
# Verifica que exista
ls .env.local

# O copia de otro proyecto
cp ..\report\.env.local .env.local
```

### Error: "PostgREST error 404"

**Causa:** Tabla `registro_st_vt_rc_reposicion` no existe en Supabase.

**Fix:**
```sql
-- Ejecutar en Supabase SQL Editor
-- Ver: control_central/migrations/060_registro_st_vt_rc_reposicion.sql
```

### Error: "No se encontraron imágenes en BD"

**Causa:** Tabla existe pero columna `imagen_nombre` está vacía.

**Fix:**
```sql
-- Verificar datos
SELECT COUNT(*), COUNT(imagen_nombre) 
FROM registro_st_vt_rc_reposicion;

-- Si COUNT(imagen_nombre) = 0, importar Excel con columna imagen
```

### "tkinter no disponible"

**Causa:** Python no tiene tkinter (GUI).

**Fix:**
```powershell
# En Windows, reinstalar Python con tcl/tk
# O ejecutar desde entorno con GUI
```

---

## Ejemplo de ejecución completa

```powershell
C:\Users\hecto\Nexus_Core\control_central> python tools\buscador_de_fotos_retail.py

======================================================================
BUSCADOR DE FOTOS RETAIL
Fuente: registro_st_vt_rc_reposicion (columna imagen_nombre)
Destino: Supabase Storage bucket 'productos'
======================================================================

Consultando registro_st_vt_rc_reposicion (Retail)...
  → 523 imágenes únicas en BD
Listando bucket Storage 'productos'...
  → 450 archivos en Storage

⚠️  3 duplicados detectados en Storage (ej: foto (1).jpg)

📊 Resumen:
  - Imágenes en BD: 523
  - Archivos en Storage: 450
  - Faltantes en Storage: 73

🔍 Buscaré 73 fotos faltantes
Seleccioná carpeta ORIGEN donde buscar las fotos...
[Ventana de selección se abre]

Buscando 73 fotos en 'D:\Fotos_Productos'...
  → 68 encontradas localmente

⚠️  5 fotos NO encontradas localmente

📋 Encontré 68 fotos
Seleccioná carpeta RESPALDO donde copiarlas antes de subir...
[Ventana de selección se abre]

Copiando 68 fotos a 'D:\Respaldo_20260611'...
  ✅ 68 fotos copiadas a respaldo

[Ventana de confirmación]
¿Subir 68 fotos a bucket 'productos'?

Subiendo 68 fotos a Storage...
  [1/68] Subiendo 1184-1101-SINT-NEGRO.jpg...
    ✅ OK
  [2/68] Subiendo 1184-1161-SINT-NEGRO.jpg...
    ✅ OK
  ...
  [68/68] Subiendo 1185-1124-CUERO-CAFE.jpg...
    ✅ OK

  ✅ 68/68 fotos subidas exitosamente

Generando reportes en 'diagnostico_fotos_retail\20260611_143022'...
  ✅ Reportes generados

======================================================================
✅ PROCESO COMPLETADO
📁 Reportes en: diagnostico_fotos_retail\20260611_143022
======================================================================
```

---

## Referencias

**Script original:**
- `tools/buscador_de_fotos.py` - Versión para Sales Report
- `.claude/2_modulos/2.1_control_central/docs/README_buscador_de_fotos.md`

**Documentación Retail:**
- `.claude/6_ot/en_curso/OT-RETAIL-ST-VT-RC-001.md` - Import Excel Retail
- `.claude/6_ot/en_curso/OT-PILARES-LEYES-IMPORTACION-001.md` - Columna imagen_nombre

**Tablet Bazzar:**
- `tablet-bazzar/ORIGEN_DATOS_RETAIL.md` - Flujo completo de datos
- `tablet-bazzar/lib/product-image.ts` - Resolución de imágenes

---

**Fecha:** 2026-06-11  
**Responsable:** Claude Code  
**Validado por:** Director
