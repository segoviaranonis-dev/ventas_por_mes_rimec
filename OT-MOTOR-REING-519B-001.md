# OT-MOTOR-REING-519B-001 — Hotfix: Preview sin SKUs + aplicar biblioteca lento

**Estado:** IMPLEMENTADO (working tree)  
**Fecha:** 2026-05-18  
**Causa OT-519:** Al pulsar **Continuar a Preview** solo se copiaba la biblioteca al evento; **no** se ejecutaba `resolver_casos_skus` (antes Paso 2).

## Síntoma director

- **Aplicando biblioteca** ~8 min (N inserts línea×caso en Supabase).
- Preview: *"No hay SKUs resueltos o matriz del listado vacía. Volvé al Paso 2."*

## Fix

1. `preparar_evento_para_preview()` en `logic.py` — contenedor + resolver SKUs.
2. `biblioteca_ui.py` — llamar tras `aplicar_biblioteca_a_evento`.
3. `ui.py` `_paso_3_preview` — recuperación automática si ya hay matriz pero faltan SKUs.
4. `_insert_lineas_contenedor_bulk` — INSERT masivo (menos round-trips al aplicar bib).
5. `lineas_union_biblioteca` — comparación usa `biblioteca_caso_linea`.

## Git

```powershell
git add modules/rimec_engine/logic.py modules/rimec_engine/biblioteca_ui.py modules/rimec_engine/ui.py modules/rimec_engine/biblioteca_compare.py modules/rimec_engine/biblioteca_maestro.py
git commit -m "fix(motor): preparar SKUs al ir a Preview desde biblioteca (OT-519B)"
git push origin main
```

## Prueba

Mismo Excel CP 6078: Comparar verde → Continuar a Preview → debe mostrar **"Se procesarán N SKUs"** y botón **Iniciar Cálculo**.
