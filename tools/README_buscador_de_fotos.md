# Buscador de fotos — herramienta auxiliar

## Objetivo

`buscador_de_fotos.py` compara las imágenes referenciadas en:

```txt
registro_ventas_general_v2
```

contra el bucket público:

```txt
Supabase Storage > productos
```

Solo trabaja por defecto con:

```txt
id_tipo = 1
```

## Qué hace

1. Busca imágenes únicas en ventas (`imagen`) para `id_tipo = 1`.
2. Lista archivos existentes en Storage `productos`.
3. Detecta duplicados tipo `(1).jpg`.
4. Calcula faltantes.
5. Pide carpeta origen donde buscar fotos.
6. Pide carpeta respaldo donde copiar las fotos encontradas.
7. Pregunta si querés subirlas a Supabase.
8. Genera CSVs de auditoría.

## Cómo ejecutarlo

Desde:

```powershell
cd C:\Users\hecto\Nexus_Core\control_central
```

Ejecutar:

```powershell
python tools\buscador_de_fotos.py
```

Modo diagnóstico sin subir:

```powershell
python tools\buscador_de_fotos.py --dry-run
```

## Variables necesarias

Debe encontrar en `.env.local` o variables de entorno:

```txt
NEXT_PUBLIC_SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Si no hay service role, intentará usar anon key, pero para subir normalmente se necesita service role.

## Salida

Genera reportes en:

```txt
diagnostico_fotos\YYYYMMDD_HHMMSS\
```

Archivos:

```txt
imagenes_db.csv
storage_duplicados.csv
faltantes_storage.csv
encontrados_local.csv
faltantes_local.csv
duplicados_local.csv
resultado_upload.csv
```

## Seguridad

- No borra duplicados.
- No borra fotos.
- No sobreescribe fotos existentes.
- Primero copia respaldo local.
- Sube solo si confirmás en ventana.
