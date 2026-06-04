# OT — Ordenes de trabajo Nexus Holding

> Rol: sistema oficial para organizar trabajo ejecutable.  
> Este directorio no reemplaza OTs históricas en la raíz; define el orden nuevo desde ahora.

---

## Carpetas

```txt
docs/ot/
  README.md
  PLANTILLA_OT.md
  INDICE_OT.md
  COLA_TRABAJO.md
  en_curso/
  cerradas/
  evidencia/
  respuestas/
```

| Carpeta | Uso |
|---|---|
| `en_curso/` | OT activas o listas para Claude Code |
| `cerradas/` | OT ejecutadas y aprobadas |
| `evidencia/` | Logs, capturas, videos, resultados |
| `respuestas/` | Reportes finales de MARTA y YAMBAI |

---

## Regla de numeración

Formato:

```txt
OT-<REPO>-<MODULO>-<NUMERO>.md
```

Ejemplos:

```txt
OT-REPORT-VENTAS-FOTOS-001.md
OT-REPORT-PDF-HOLDING-002.md
OT-REPORT-PDF-ESTADISTICAS-003.md
OT-RIMEC-WEB-CATALOGO-PDF-001.md
OT-BAZZAR-CHECKOUT-STOCK-001.md
```

---

## Flujo

1. GPT redacta OT.
2. OT entra en `en_curso/`.
3. La OT se registra en `COLA_TRABAJO.md` para MARTA o YAMBAI.
4. El albañil ejecuta la primera OT `LISTA_PARA_EJECUTAR`.
5. Evidencia se guarda en `evidencia/`.
6. Respuesta se guarda en `respuestas/<ALBANIL>/`.
7. GPT verifica.
8. Si pasa, OT se mueve a `cerradas/`.
9. Se actualizan `INDICE_OT.md` y `COLA_TRABAJO.md`.

---

## Estado permitido

| Estado | Significado |
|---|---|
| `BORRADOR` | Aun no ejecutable |
| `LISTA_PARA_CLAUDE` | Puede copiarse a Claude Code |
| `EN_EJECUCION` | Claude Code trabajando |
| `EN_REVISION_GPT` | Pendiente de verificación |
| `CORRECCION_REQUERIDA` | Falló verificación |
| `CERRADA` | Aprobada |

---

## Regla de oro

Sin OT o instrucción directa clara, no se toca código crítico.

---

## Comandos humanos

El Director puede decir:

```txt
MARTA, ejecutá tu OT pendiente.
YAMBAI, ejecutá tu OT pendiente.
```

Y al terminar:

```txt
MARTA terminó.
YAMBAI terminó.
```

GPT buscará la respuesta en `COLA_TRABAJO.md`.
