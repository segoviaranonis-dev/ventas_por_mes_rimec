# Nexus Core — Guía rápida para agentes

**OPTIMIZADO**: Este archivo contiene solo lo esencial. Docs completos bajo demanda.

## Reglas de oro

1. **Pilares (5 FK)**: `linea_id`, `referencia_id`, `material_id`, `color_id`, `talla_id` → `combinacion`
2. **Nomenclatura P0**: `codigo_proveedor` en maestros, `{pilar}_codigo_proveedor` en copias
3. **No usar**: `linea.caso_id` como fuente nueva, `linea_codigo`/`ref_cod` (legacy)
4. **No mezclar**: Sales Report (`registro_ventas_general_v2`) con pilares operativos
5. **No tocar sin OT**: Flujo FK/Eventos Nexus → RIMEC Web → Bazzar Web
6. **Imports largos**: latido cada 60seg, celebrar con `core.ux_celebrate` tras éxito
7. **Commits**: NUEVOS (no `--amend`), incluir `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
8. **Testing**: Probar UI/features en browser antes de reportar éxito

## Metodología

- **GPT**: planifica, supervisa, audita, redacta OT
- **Claude Code (tú)**: ejecuta, prueba, evidencia

## Repos del holding

- **control_central** (este): Streamlit operativo, motor precios, IC/PP/FI/Compra Legal
- **rimec-web**: Next.js vendedores (catálogo mayorista, stock en tránsito)
- **report**: Next.js reportes institucionales (ventas, stock, retail)
- **bazzar-web**: E-commerce final (reservas, pedidos web)

## Documentación completa (leer SOLO si necesario)

- Arquitectura: `docs/NEXUS_HOLDING_REGLAS_CANONICAS.md`
- Protocolo trabajo: `docs/NEXUS_HOLDING_PROTOCOLO_CLAUDE_CODE.md`
- Pilares detalle: `docs/RIMEC_PILARES_CINCO.md` + `docs/RIMEC_NOMENCLATURA_PILARES.md`
- OT activas: `docs/ot/INDICE_OT.md`
- Índice general: `docs/NEXUS_CORE_INDEX.md`

---
*Optimizado para reducir tokens. Si algo no está claro, preguntar al Director antes de asumir.*
