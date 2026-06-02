# Nexus Core — Protocolo unico de imagenes de producto

## Ley

Todas las apps del ecosistema deben resolver imagenes de calzado desde el mismo contrato:

```text
Supabase Storage bucket: productos
Archivo canonico: linea-referencia-material-color.jpg
```

Ejemplo:

```text
4076-1350-9569-15745.jpg
```

## Que significa cada parte

| Posicion | Dato | Fuente |
|---|---|---|
| 1 | linea | `linea.codigo_proveedor` |
| 2 | referencia | `referencia.codigo_proveedor` |
| 3 | material | codigo proveedor/F9 del material |
| 4 | color | codigo proveedor/F9 del color |

No usar IDs internos Nexus para construir el nombre del archivo.

## URL publica

Las apps construyen la URL asi:

```text
NEXT_PUBLIC_SUPABASE_URL/storage/v1/object/public/productos/linea-referencia-material-color.jpg
```

La URL de Supabase debe limpiarse antes de usarla porque en Windows/Vercel puede venir mal pegada.

## Reglas por app

### Report / Ventas con fotos

Puede recibir el nombre de archivo desde la venta legacy y parsearlo.
Si el archivo ya existe como `4076-1350-9569-15745.jpg`, solo debe apuntar al bucket `productos`.

### RIMEC Web

Debe usar la misma formula con linea, referencia, material y color.

### Bazzar Web

Debe usar:

1. `imagen_url` si ya viene completa o como path valido.
2. Si no viene, construir con:
   - `linea_codigo`
   - `referencia_codigo`
   - `material_code` o `id_material_f9`
   - `color_code` o `id_color_f9`

Prohibido caer a `material_id` o `color_id` para imagenes, porque esos pueden ser IDs internos y no coincidir con el archivo real.

## Motivo

Las fotos vienen del flujo Nexus/Rene y viven en Supabase Storage. Si cada app inventa su propia formula, aparecen errores falsos: la foto existe, pero la app la busca con otro nombre.

## Regla para agentes

Antes de tocar imagenes:

1. Verificar si existe un helper local de imagenes.
2. No construir URLs a mano dentro de componentes.
3. No usar service role ni API privada para leer imagenes publicas.
4. No cambiar el formato del archivo sin migracion planificada.
