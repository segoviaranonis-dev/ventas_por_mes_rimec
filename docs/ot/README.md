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
  en_curso/
  cerradas/
  evidencia/
```

| Carpeta | Uso |
|---|---|
| `en_curso/` | OT activas o listas para Claude Code |
| `cerradas/` | OT ejecutadas y aprobadas |
| `evidencia/` | Logs, capturas, videos, resultados |

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
3. Claude Code ejecuta.
4. Evidencia se guarda en `evidencia/`.
5. GPT verifica.
6. Si pasa, OT se mueve a `cerradas/`.
7. Se actualiza `INDICE_OT.md`.

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
