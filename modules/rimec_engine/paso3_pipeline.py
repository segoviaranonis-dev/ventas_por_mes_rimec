"""
Paso 3 — pipeline de negocio (sin Streamlit).
Transacciones cortas por caso + liberación explícita del pool SQLAlchemy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from core.database import engine
from modules.rimec_engine.logic import (
    actualizar_caso_evento,
    asegurar_contenedor_lineas_excel,
    build_pillar_cache,
    calcular_precio_lista_sql,
    cargar_staging_precio_lista,
    crear_caso,
    guardar_precio_lista,
    limpiar_staging_precio_lista,
    parse_lineas_array,
    parse_marcas_array,
    prefetch_materiales_para_listado,
    prefetch_pilares_faltantes_listado,
    preparar_filas_staging_bulk,
    reemplazar_lineas_excepcion,
)


def _to_float(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
from modules.rimec_engine.ui_paso3_live import Paso3Metrics, TickFn

ProgressFn = Callable[[dict[str, Any]], None]


def liberar_conexiones_paso3() -> None:
    """Devuelve conexiones al pool tras cada ciclo (evita bloqueo driver)."""
    try:
        engine.pool.dispose()
    except Exception:
        pass


def _emit(tick: TickFn | None, metrics: Paso3Metrics, **kw: Any) -> None:
    for k, v in kw.items():
        setattr(metrics, k, v)
    if tick:
        tick(metrics)


def verificar_conexion_db() -> tuple[bool, str | None]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        liberar_conexiones_paso3()
        return True, None
    except Exception as exc:
        return False, str(exc)


@dataclass
class Paso3PipelineResult:
    ok: bool = False
    total_guardados: int = 0
    error: str | None = None
    casos_procesados: list = field(default_factory=list)
    confirmados: dict = field(default_factory=dict)
    skus_omitidos_total: int = 0
    stats_pilar: dict = field(default_factory=dict)
    resultado_sql: dict | None = None


def procesar_caso_paso3_aislado(
    *,
    metrics: Paso3Metrics,
    tick: TickFn | None,
    nombre_caso: str,
    caso_idx: int,
    skus_grupo: pd.DataFrame,
    caso_params: dict,
    caso_db: dict,
    evento_id: int,
    proveedor_id: int,
    cache: dict,
    usar_sql: bool,
) -> dict[str, Any]:
    """
    Un caso = varias transacciones cortas; pool liberado entre pasos.
    """
    out: dict[str, Any] = {
        "ok": False,
        "caso_id": None,
        "filas": [],
        "omitidos": 0,
        "n_contenedor": 0,
        "error": None,
    }
    lineas_ev = caso_db.get("lineas") or []

    _emit(
        tick,
        metrics,
        subfase="persistir caso en BD",
    )
    metrics.log(f"Caso «{nombre_caso}»: guardando parámetros…")

    caso_db_id = caso_params.get("caso_db_id")
    if caso_db_id is not None and not (isinstance(caso_db_id, float) and pd.isna(caso_db_id)):
        caso_id = int(caso_db_id)
        if not actualizar_caso_evento(caso_id, caso_db):
            out["error"] = f"Fallo al actualizar caso {nombre_caso}."
            return out
    else:
        caso_id = crear_caso(evento_id, caso_db)
        if not caso_id:
            out["error"] = f"Fallo al guardar configuración del caso {nombre_caso}."
            return out
    out["caso_id"] = caso_id
    liberar_conexiones_paso3()

    if lineas_ev:
        _emit(tick, metrics, subfase="contenedor líneas")
        metrics.log(f"Caso «{nombre_caso}»: contenedor ({len(lineas_ev)} códigos)…")
        out["n_contenedor"] = reemplazar_lineas_excepcion(
            caso_id, lineas_ev, proveedor_id, evento_id
        )
        liberar_conexiones_paso3()
        print(
            f"[ENGINE] Contenedor línea→caso '{nombre_caso}': {out['n_contenedor']} filas"
        )

    def on_prep(prog: dict[str, Any]) -> None:
        phase = prog.get("phase", "")
        if phase == "normalize":
            _emit(tick, metrics, subfase="normalizando códigos Excel")
        elif phase == "resolve_fk":
            _emit(
                tick,
                metrics,
                subfase=f"resolviendo FK ({prog.get('validos', 0)} válidos)",
                validos_caso=int(prog.get("validos", 0)),
            )
        elif phase == "build_rows":
            _emit(
                tick,
                metrics,
                subfase="armando filas en memoria",
                filas_caso=int(prog.get("filas", 0)),
                validos_caso=int(prog.get("validos", 0)),
            )

    _emit(tick, metrics, subfase="preparación bulk en memoria")
    metrics.log(f"Caso «{nombre_caso}»: preparando {len(skus_grupo)} SKUs…")

    filas, omitidos = preparar_filas_staging_bulk(
        skus_grupo,
        evento_id=evento_id,
        caso_id=caso_id,
        cache=cache,
        caso_db=caso_db,
        usar_sql=usar_sql,
        on_progress=on_prep,
    )
    out["filas"] = filas
    out["omitidos"] = omitidos

    if usar_sql and filas:
        _emit(tick, metrics, subfase="INSERT staging (transacción única)")
        metrics.log(f"Caso «{nombre_caso}»: staging +{len(filas)} filas")
        cargar_staging_precio_lista(filas, evento_id=evento_id)
        liberar_conexiones_paso3()
    elif filas:
        _emit(tick, metrics, subfase="INSERT precio_lista")
        guardar_precio_lista(filas)
        liberar_conexiones_paso3()

    out["ok"] = True
    return out


def ejecutar_pipeline_paso3(
    *,
    tick: TickFn | None,
    metrics: Paso3Metrics,
    evento_id: int,
    proveedor_id: int,
    skus_resueltos: pd.DataFrame,
    df_evento: pd.DataFrame,
    casos_bib: dict,
    stats_pilar: dict,
    usar_sql: bool = True,
) -> Paso3PipelineResult:
    """Orquestación completa Paso 3 — sin widgets Streamlit."""
    res = Paso3PipelineResult(stats_pilar=stats_pilar)
    grupos = list(skus_resueltos.groupby("caso_asignado"))
    metrics.casos_total = len(grupos)
    metrics.skus_total = len(skus_resueltos)

    _emit(tick, metrics, fase="Contenedor automático", subfase="líneas Excel")
    n_auto = asegurar_contenedor_lineas_excel(
        evento_id, proveedor_id, skus_resueltos, df_evento
    )
    if n_auto:
        metrics.log(f"Contenedor auto: +{n_auto} línea(s)")
    liberar_conexiones_paso3()

    _emit(tick, metrics, fase="Caché de pilares", subfase="consulta masiva")
    metrics.log("Cargando caché de pilares (3 consultas)…")
    cache = build_pillar_cache(proveedor_id, skus_resueltos)
    liberar_conexiones_paso3()

    _emit(tick, metrics, fase="Prefetch materiales", subfase="transacción única")
    prefetch_materiales_para_listado(cache, proveedor_id, skus_resueltos)
    liberar_conexiones_paso3()

    _emit(tick, metrics, fase="Prefetch pilares faltantes", subfase="códigos únicos")
    prefetch_pilares_faltantes_listado(cache, proveedor_id, skus_resueltos)
    liberar_conexiones_paso3()

    if usar_sql:
        _emit(tick, metrics, fase="Staging", subfase="limpiar evento previo")
        limpiar_staging_precio_lista(evento_id)
        liberar_conexiones_paso3()

    staging_acum = 0
    for i, (nombre_caso, skus_grupo) in enumerate(grupos):
        metrics.caso_idx = i + 1
        metrics.caso_actual = str(nombre_caso)
        metrics.skus_caso = len(skus_grupo)
        _emit(tick, metrics, fase="Procesando casos", subfase="inicio ciclo")
        print(f"[ENGINE] Iniciando cálculo de caso: '{nombre_caso}' ({len(skus_grupo)} SKUs)")

        if nombre_caso not in casos_bib:
            res.error = f"Caso '{nombre_caso}' no está en la matriz del listado."
            metrics.log(f"ERROR: {res.error}")
            if tick:
                tick(metrics)
            return res

        caso_params = casos_bib[nombre_caso]
        marcas_ev = parse_marcas_array(caso_params.get("marcas"))
        lineas_ev = parse_lineas_array(caso_params.get("lineas"))
        caso_db = {
            "nombre_caso": caso_params["nombre_caso"],
            "dolar_politica": _to_float(caso_params.get("dolar_politica")) or 8000.0,
            "factor_conversion": _to_float(caso_params.get("factor_conversion")) or 180.0,
            "descuento_1": _to_float(caso_params.get("descuento_1")),
            "descuento_2": _to_float(caso_params.get("descuento_2")),
            "descuento_3": _to_float(caso_params.get("descuento_3")),
            "descuento_4": _to_float(caso_params.get("descuento_4")),
            "genera_lpc03_lpc04": bool(caso_params.get("genera_lpc03_lpc04", True)),
            "regla_redondeo": "centena",
            "marcas": marcas_ev if marcas_ev else None,
            "lineas": lineas_ev,
            "referencias": [],
            "alcance_tipo": str(caso_params.get("alcance_tipo") or "marcas"),
        }

        ciclo = procesar_caso_paso3_aislado(
            metrics=metrics,
            tick=tick,
            nombre_caso=str(nombre_caso),
            caso_idx=i,
            skus_grupo=skus_grupo,
            caso_params=caso_params,
            caso_db=caso_db,
            evento_id=evento_id,
            proveedor_id=proveedor_id,
            cache=cache,
            usar_sql=usar_sql,
        )
        if ciclo.get("error"):
            res.error = ciclo["error"]
            metrics.log(f"ERROR: {res.error}")
            if tick:
                tick(metrics)
            return res

        res.casos_procesados.append(caso_db)
        n_filas = len(ciclo["filas"])
        res.skus_omitidos_total += int(ciclo["omitidos"])
        res.confirmados[f"caso_{i}"] = n_filas
        staging_acum += n_filas
        metrics.skus_preparados += len(skus_grupo)
        metrics.staging_acum = staging_acum
        metrics.omitidos = res.skus_omitidos_total
        metrics.log(
            f"Caso «{nombre_caso}» OK — {n_filas} filas, {ciclo['omitidos']} omitidos"
        )
        if tick:
            tick(metrics)
        print(
            f"[ENGINE] Completado caso '{nombre_caso}' "
            f"({len(skus_grupo)} SKUs, {n_filas} guardados)."
        )

    if usar_sql and staging_acum > 0:
        _emit(tick, metrics, fase="Cálculo SQL masivo", subfase="función Postgres")
        metrics.log(f"Ejecutando SQL sobre {staging_acum} SKUs en staging…")
        res.resultado_sql = calcular_precio_lista_sql(evento_id)
        liberar_conexiones_paso3()
        err = res.resultado_sql.get("error")
        total_sql = int(res.resultado_sql.get("total") or 0)
        if err:
            res.error = str(err)
            res.ok = False
        elif total_sql <= 0:
            res.error = "Cálculo SQL insertó 0 precios."
            res.ok = False
        else:
            res.total_guardados = total_sql
            res.ok = True
            limpiar_staging_precio_lista(evento_id)
            liberar_conexiones_paso3()
            metrics.log(f"SQL OK — {total_sql:,} precios")
    elif not usar_sql:
        res.total_guardados = sum(res.confirmados.values())
        res.ok = res.total_guardados > 0
    else:
        res.error = "No hay filas en staging para calcular."
        res.ok = False

    _emit(tick, metrics, fase="Completado" if res.ok else "Error", subfase="")
    if tick:
        tick(metrics)
    return res
