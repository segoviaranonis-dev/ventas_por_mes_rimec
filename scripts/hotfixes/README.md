# Scripts de Hotfixes

Esta carpeta contiene scripts de hotfixes urgentes aplicados en producción.

## Índice

### 2026-06-10: PP-2026-0012

**Problema:** PP en estado ENVIADO sin autorización, bloqueando 7,756 pares.

**Scripts:**
- `HOTFIX_PP_2026_0012.py` - Cambio de estado ENVIADO → ABIERTO
- `HOTFIX_DESVINCULAR_PP_0012.py` - Desvinculación de compras
- `buscar_pp_0012.py` - Diagnóstico
- `verificar_pp_0012.py` - Verificación post-hotfix

**Documentación:** `docs/HOTFIX_2026_06_10_PP_0012.md`

**Estado:** ✅ COMPLETADO

---

**Nota:** Estos scripts son de referencia histórica. NO ejecutar sin revisar la documentación completa.
