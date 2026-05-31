# Nexus Holding — Protocolo de comunicación con Claude Code

> Rol: contrato de trabajo entre Director, GPT y Claude Code.  
> Objetivo: evitar ejecuciones ambiguas, cambios fuera de alcance y falsas validaciones.

---

## 1. Cadena de mando

```txt
Director -> GPT -> COLA_TRABAJO.md -> MARTA/YAMBAI -> respuesta/evidencia -> GPT verifica -> Director decide
```

Claude Code puede proponer, pero no debe cambiar la estrategia sin aprobación.

### Albañiles

| Albañil | Herramienta | Frente |
|---|---|---|
| MARTA | Cursor Desktop | `report` |
| YAMBAI | Claude Code | Nexus operativo |

---

## 2. Mensaje ideal para Claude Code

Cada orden debe tener esta forma:

```txt
OC/OT: <ID>
Repo: <repo>
Rama: <rama o base>
Objetivo:
Alcance permitido:
No tocar:
Reglas de negocio:
Pasos:
Pruebas obligatorias:
Evidencia requerida:
Criterio de cierre:
```

---

## 3. Palabras reservadas

| Palabra | Significado |
|---|---|
| **NO TOCAR** | Archivo/modulo prohibido |
| **DETENERSE** | Parar y reportar; no improvisar |
| **VERIFICAR ANTES** | Consultar esquema/datos antes de editar |
| **EVIDENCIA** | Screenshot, video, log o salida de comando |
| **CANÓNICO** | Regla que manda |
| **LEGACY** | Existe, pero no debe guiar diseño nuevo |

---

## 4. Formato de respuesta obligatorio de Claude Code

Claude Code / Cursor debe responder usando `docs/ot/PLANTILLA_RESPUESTA_ALBANIL.md`:

```txt
Resumen:
- Qué hice

Archivos tocados:
- ruta

Pruebas:
- comando
- resultado

Evidencia:
- screenshot/video/log

Riesgos:
- lo que queda pendiente

Commit/PR:
- hash
- rama
- PR si existe
```

Si no hay pruebas, debe decir: `No validado` y explicar por qué.

La respuesta final debe guardarse en:

```txt
docs/ot/respuestas/<ALBANIL>/<OT_ID>_RESPUESTA.md
```

---

## 5. Protocolo antes de tocar base de datos

Claude Code debe:

1. mostrar SQL;
2. explicar impacto;
3. verificar si la tabla/columna existe;
4. hacer SQL idempotente;
5. indicar rollback;
6. ejecutar solo si la OT lo autoriza;
7. guardar archivo `.sql` en repo.

Ejemplo mínimo:

```sql
CREATE TABLE IF NOT EXISTS ...
```

No se aceptan cambios manuales sin archivo versionado.

---

## 6. Protocolo antes de tocar seguridad

Cambios de seguridad requieren:

- alcance explícito;
- rollback;
- prueba de login;
- no mezclar con UI;
- no commitear secretos;
- no inventar auth nueva si ya existe contrato.

Si el cambio puede dejar usuarios sin acceso, Claude debe detenerse y pedir validación.

---

## 7. Protocolo para errores

Si aparece un error:

1. copiar error completo;
2. indicar paso exacto;
3. ubicar archivo probable;
4. formular hipótesis;
5. probar la hipótesis;
6. recién después modificar.

Prohibido:

- "arreglar" por intuición sin verificar esquema;
- cambiar tipos de datos sin confirmar;
- tapar error con fallback silencioso;
- reportar éxito si el flujo falló una vez y luego funcionó por casualidad.

---

## 8. Protocolo para Report / Ventas con Fotos

Reglas específicas:

- Repo: `report`.
- Fuente ventas: `registro_ventas_general_v2`.
- Tipo: CALZADOS, `tipo_v2.id_tipo = 1`.
- `imagen` es molécula `linea-referencia-material-color.jpg`.
- Foto desde Supabase Storage bucket `productos`.
- No tocar `rimec-web` ni `bazzar-web`.
- No tocar Sales Report principal si la OT es de `ventas-fotos`.
- PDF debe reutilizar arquitectura segura de `rimec-web`, no Puppeteer.

---

## 9. Protocolo para ramas y commits

Claude Code debe:

1. revisar `git status`;
2. no pisar cambios no propios;
3. crear rama si corresponde;
4. commit por unidad lógica;
5. push;
6. informar hash.

Si trabaja local en `main`, debe decirlo explícitamente.

---

## 10. Checklist de aceptación

Una OT no se considera cerrada hasta que:

- el código está commiteado;
- pruebas pasan o limitación está explicada;
- evidencia existe;
- GPT revisó;
- Director acepta o pide corrección;
- OT se mueve a cerrada.

---

## 11. Mensaje corto para iniciar una OT

```txt
Claude, ejecutar OT adjunta sin salir del alcance.
Antes de editar: git status, leer reglas canónicas y confirmar archivos objetivo.
Si encuentras conflicto de datos o esquema, detenerte y reportar.
No tocar módulos fuera de "No tocar".
```

---

## 12. Regla final

Claude Code ejecuta. GPT gobierna arquitectura. El Director manda el negocio.
