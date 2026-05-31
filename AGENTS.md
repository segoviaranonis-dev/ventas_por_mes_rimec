# Nexus Core — instrucciones para agentes

Antes de modificar código o documentación, leer:

1. `docs/NEXUS_CORE_INDEX.md`
2. `docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md`
3. `docs/NEXUS_HOLDING_REGLAS_CANONICAS.md`
4. `docs/NEXUS_HOLDING_MANUAL_PROCEDIMIENTOS.md`
5. `docs/NEXUS_HOLDING_PROTOCOLO_CLAUDE_CODE.md`
6. `.cursor/rules/*.mdc`

## Rol de este repo

`ventas_por_mes_rimec` es la casa operativa de Nexus:

- Streamlit administrativo;
- Motor de precios;
- IC / PP / FI / Compra Legal / Depósito;
- reglas de pilares;
- documentación canónica del holding.

## Reglas rápidas

- No usar `linea.caso_id` como fuente nueva de caso comercial.
- No mezclar Sales Report con pilares.
- No cambiar nomenclatura P0 sin migración y documento.
- No borrar OTs ni evidencia histórica.
- Imports largos deben tener latido cada 60 segundos.
- UI Streamlit debe celebrar escrituras exitosas con `core.ux_celebrate`.

## Metodología IA

- GPT conversa, planifica, audita y supervisa.
- Claude Code ejecuta cambios concretos.
- Si una orden afecta arquitectura, primero redactar una OT o checklist.
- Cola operativa: `docs/ot/COLA_TRABAJO.md`.
- Respuestas obligatorias: `docs/ot/respuestas/<ALBANIL>/<OT_ID>_RESPUESTA.md`.
