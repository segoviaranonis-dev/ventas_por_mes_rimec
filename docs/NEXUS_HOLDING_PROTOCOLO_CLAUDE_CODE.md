# Nexus Holding — Protocolo de comunicación con MARTA y YAMBAI

## Cadena de mando

Director -> GPT -> COLA_TRABAJO.md -> MARTA/YAMBAI -> respuesta/evidencia -> GPT verifica -> Director decide

## Roles

| Albañil | Herramienta | Frente |
|---|---|---|
| MARTA | Cursor Desktop | report |
| YAMBAI | Claude Code | Nexus operativo |

## Regla principal

MARTA y YAMBAI ejecutan OT concretas. No improvisan arquitectura.

## Formato obligatorio de respuesta

Toda respuesta debe guardarse en:

docs/ot/respuestas/<ALBANIL>/<OT_ID>_RESPUESTA.md

Debe incluir:

- Resumen
- Archivos tocados
- Pruebas
- Evidencia
- Riesgos
- Commit / rama / push
- Siguiente acción sugerida

## Evidencia

La evidencia va en:

docs/ot/evidencia/<OT_ID>/

## Comandos humanos

Héctor puede decir:

MARTA, ejecutá tu OT pendiente.
YAMBAI, ejecutá tu OT pendiente.

Cuando terminen:

MARTA terminó.
YAMBAI terminó.
