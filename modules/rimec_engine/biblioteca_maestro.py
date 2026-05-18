"""
Maestro Biblioteca de Casos — lógica de negocio y motor de descarte en memoria.

Exclusividad en la biblioteca: cada línea del pilar pertenece como máximo a un caso
dentro de la misma biblioteca. El pilar en sí no impone esa regla; la impone el maestro.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sqlalchemy import text

from core.database import DBInspector, commit_query, engine, get_dataframe
from modules.rimec_engine.logic import (
    _caso_dict_para_db,
    normalizar_caso_evento,
    parse_lineas_array,
    parse_marcas_array,
    persistir_caso_matriz_evento,
    vaciar_matriz_evento,
)


# ─────────────────────────────────────────────────────────────────────────────
# Motor en memoria (latencia < 1s en selector «Agregar línea»)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BibliotecaEditorState:
    """Estado editable de una biblioteca en sesión Streamlit."""

    proveedor_id: int
    biblioteca_id: int | None
    nombre: str
    casos: dict[str, dict[str, Any]] = field(default_factory=dict)
    pilar_lineas: list[str] = field(default_factory=list)
    pilar_marca_por_codigo: dict[str, int | None] = field(default_factory=dict)
    pilar_marcas: dict[int, str] = field(default_factory=dict)
    pilar_tiene_sin_marca: bool = False
    dirty: bool = False

    _SIN_MARCA_FK = -1

    def etiquetas_marcas_pilar(self) -> list[tuple[int, str]]:
        """Catálogo completo del pilar (sin descartar líneas ocupadas)."""
        out = [(mid, nom) for mid, nom in sorted(
            self.pilar_marcas.items(), key=lambda x: x[1].casefold()
        )]
        if self.pilar_tiene_sin_marca:
            out.insert(0, (self._SIN_MARCA_FK, "— Sin marca —"))
        return out

    def todas_lineas_ocupadas(self) -> set[str]:
        ocupadas: set[str] = set()
        for data in self.casos.values():
            ln = data.get("lineas") or set()
            if isinstance(ln, set):
                ocupadas |= ln
            else:
                ocupadas |= set(ln)
        return ocupadas

    def resumen_lineas_biblioteca(self) -> tuple[int, int, int]:
        """(líneas pilar, asignadas en casos de la biblioteca, libres)."""
        n_pilar = len(self.pilar_lineas)
        n_asig = len(self.todas_lineas_ocupadas())
        return n_pilar, n_asig, max(0, n_pilar - n_asig)

    def lineas_ocupadas_en_otros_casos(self, caso_nombre: str) -> set[str]:
        """Líneas ya asignadas a cualquier otro caso de esta biblioteca."""
        clave_actual = self._clave_caso(caso_nombre)
        ocupadas: set[str] = set()
        for key, data in self.casos.items():
            if key == clave_actual:
                continue
            ln = data.get("lineas") or set()
            if isinstance(ln, set):
                ocupadas |= ln
            else:
                ocupadas |= set(ln)
        return ocupadas

    def lineas_huerfanas_nuevo_caso(self) -> list[str]:
        """Pilar menos líneas ya usadas en casos existentes (caso nuevo vacío)."""
        return self.lineas_disponibles_para("__caso_nuevo__")

    def marcas_en_lineas(self, codigos: list[str]) -> list[tuple[int, str]]:
        """Marcas (fk) con al menos una línea en el pool indicado (p. ej. huérfanas)."""
        mids_vistos: set[int] = set()
        out: list[tuple[int, str]] = []
        hay_sin_marca = False
        for cod in codigos:
            mid = self.pilar_marca_por_codigo.get(cod)
            if mid is None:
                hay_sin_marca = True
                continue
            mid_i = int(mid)
            if mid_i not in mids_vistos:
                nom = self.pilar_marcas.get(mid_i)
                if nom:
                    mids_vistos.add(mid_i)
                    out.append((mid_i, nom))
        out.sort(key=lambda x: x[1].casefold())
        if hay_sin_marca:
            out.insert(0, (self._SIN_MARCA_FK, "— Sin marca —"))
        return out

    def filtrar_codigos_por_marca_fk(
        self,
        codigos: list[str],
        marca_fk_sel: list[int],
    ) -> list[str]:
        if not marca_fk_sel:
            return codigos
        permitidos: set[int | None] = set()
        for mid in marca_fk_sel:
            if mid == self._SIN_MARCA_FK:
                permitidos.add(None)
            else:
                permitidos.add(int(mid))
        return [
            c
            for c in codigos
            if self.pilar_marca_por_codigo.get(c) in permitidos
        ]

    def lineas_en_caso(self, caso_nombre: str) -> set[str]:
        clave = self._clave_caso(caso_nombre)
        data = self.casos.get(clave, {})
        ln = data.get("lineas") or set()
        return set(ln) if not isinstance(ln, set) else ln

    def lineas_disponibles_para(self, caso_nombre: str) -> list[str]:
        """Pilar menos líneas en otros casos y menos las ya cargadas en este caso."""
        en_este = self.lineas_en_caso(caso_nombre)
        en_otros = self.lineas_ocupadas_en_otros_casos(caso_nombre)
        bloqueadas = en_este | en_otros
        libres = [c for c in self.pilar_lineas if c not in bloqueadas]

        def _sort_key(c: str) -> tuple:
            try:
                return (0, int(c))
            except ValueError:
                return (1, c)

        return sorted(libres, key=_sort_key)

    def quitar_linea(self, caso_nombre: str, codigo: str) -> bool:
        """Quita una línea del contenedor del caso en memoria. Retorna False si no existía."""
        try:
            cod = str(int(float(str(codigo).strip())))
        except (ValueError, TypeError):
            return False
        clave = self._clave_caso(caso_nombre)
        if clave not in self.casos:
            return False
        lineas = self.casos[clave].get("lineas") or set()
        if isinstance(lineas, list):
            lineas = set(lineas)
        if cod not in lineas:
            return False
        lineas.discard(cod)
        self.casos[clave]["lineas"] = lineas
        self.dirty = True
        return True

    def agregar_linea(self, caso_nombre: str, codigo: str) -> tuple[bool, str]:
        cod = str(codigo).strip()
        try:
            cod = str(int(float(cod)))
        except (ValueError, TypeError):
            return False, "Código de línea inválido."
        if cod not in self.pilar_lineas:
            return False, f"Línea {cod} no existe en el pilar del proveedor."
        if cod in self.lineas_en_caso(caso_nombre):
            return False, f"Línea {cod} ya está en este caso."
        if cod in self.lineas_ocupadas_en_otros_casos(caso_nombre):
            return False, (
                f"Línea {cod} ya está asignada a otro caso de esta biblioteca."
            )
        clave = self._clave_caso(caso_nombre)
        if clave not in self.casos:
            return False, "Caso no encontrado."
        lineas = self.casos[clave].setdefault("lineas", set())
        if isinstance(lineas, list):
            lineas = set(lineas)
        lineas.add(cod)
        self.casos[clave]["lineas"] = lineas
        self.dirty = True
        return True, ""

    def agregar_lineas(self, caso_nombre: str, codigos: list[str]) -> list[str]:
        errores: list[str] = []
        for c in codigos:
            ok, msg = self.agregar_linea(caso_nombre, c)
            if not ok and msg:
                errores.append(msg)
        return errores

    def quitar_lineas(self, caso_nombre: str, codigos: list[str]) -> int:
        n = 0
        for c in codigos:
            if self.quitar_linea(caso_nombre, c):
                n += 1
        return n

    def vaciar_lineas_caso(self, caso_nombre: str) -> int:
        clave = self._clave_caso(caso_nombre)
        if clave not in self.casos:
            return 0
        n = len(self.casos[clave].get("lineas") or set())
        self.casos[clave]["lineas"] = set()
        self.dirty = True
        return n

    def validar_exclusividad_global(self) -> list[str]:
        owner: dict[str, str] = {}
        conflictos: list[str] = []
        for nombre, data in self.casos.items():
            for cod in data.get("lineas") or []:
                prev = owner.get(cod)
                if prev and prev != nombre:
                    conflictos.append(f"Línea {cod}: «{prev}» y «{nombre}»")
                else:
                    owner[cod] = nombre
        return conflictos

    def to_casos_normalizados(self) -> list[dict]:
        out: list[dict] = []
        for _clave, data in self.casos.items():
            rec = dict(data)
            lineas = rec.get("lineas") or set()
            rec["lineas"] = sorted(
                lineas,
                key=lambda x: (len(x), int(x) if str(x).isdigit() else x),
            )
            out.append(normalizar_caso_evento(rec))
        return out

    @staticmethod
    def _clave_caso(nombre: str) -> str:
        return nombre.strip().upper()

    def ensure_caso(self, nombre: str, params: dict | None = None) -> str:
        clave = self._clave_caso(nombre)
        if clave not in self.casos:
            base = dict(params or {})
            base.setdefault("nombre_caso", nombre.strip())
            base.setdefault("lineas", set())
            self.casos[clave] = base
            self.dirty = True
        elif params:
            self.casos[clave].update(params)
            if "lineas" in params:
                ln = params["lineas"]
                self.casos[clave]["lineas"] = (
                    set(ln) if not isinstance(ln, set) else ln
                )
            self.dirty = True
        return clave


def parse_codigos_linea_texto(texto: str) -> tuple[list[str], list[str]]:
    """Parsea códigos/rangos sin exigir que existan en el pilar (alta de líneas nuevas)."""
    ok: list[str] = []
    errores: list[str] = []
    if not texto or not str(texto).strip():
        return ok, errores
    raw = str(texto).replace(";", ",").replace("\n", ",")
    vistos: set[str] = set()
    for parte in raw.split(","):
        p = parte.strip()
        if not p:
            continue
        if "-" in p:
            try:
                a, b = p.split("-", 1)
                desde, hasta = int(a.strip()), int(b.strip())
                if desde > hasta:
                    desde, hasta = hasta, desde
                for n in range(desde, hasta + 1):
                    cod = str(n)
                    if cod not in vistos:
                        vistos.add(cod)
                        ok.append(cod)
            except ValueError:
                errores.append(f"Rango inválido: {p}")
        else:
            try:
                cod = str(int(float(p)))
                if cod not in vistos:
                    vistos.add(cod)
                    ok.append(cod)
            except (ValueError, TypeError):
                errores.append(f"Código inválido: {p}")
    return ok, errores


def parse_lineas_texto_pilar(
    texto: str,
    pilar_lineas: list[str],
    ocupadas: set[str],
) -> tuple[list[str], list[str]]:
    """
    Parsea '520,1122' o '520-530' o mezcla. Retorna (codigos_ok, errores).
    Solo incluye líneas que existen en pilar y no están ocupadas.
    """
    pilar_set = set(pilar_lineas)
    ok: list[str] = []
    errores: list[str] = []
    if not texto or not str(texto).strip():
        return ok, errores

    raw = str(texto).replace(";", ",").replace("\n", ",")
    for parte in raw.split(","):
        p = parte.strip()
        if not p:
            continue
        if "-" in p:
            try:
                a, b = p.split("-", 1)
                desde, hasta = int(a.strip()), int(b.strip())
                if desde > hasta:
                    desde, hasta = hasta, desde
                for n in range(desde, hasta + 1):
                    cod = str(n)
                    _clasificar_linea(cod, pilar_set, ocupadas, ok, errores)
            except ValueError:
                errores.append(f"Rango inválido: {p}")
        else:
            try:
                cod = str(int(float(p)))
                _clasificar_linea(cod, pilar_set, ocupadas, ok, errores)
            except (ValueError, TypeError):
                errores.append(f"Código inválido: {p}")
    return ok, errores


def _clasificar_linea(
    cod: str,
    pilar_set: set[str],
    ocupadas: set[str],
    ok: list[str],
    errores: list[str],
) -> None:
    if cod not in pilar_set:
        errores.append(f"Línea {cod} no está en el pilar")
        return
    if cod in ocupadas:
        errores.append(f"Línea {cod} ya está asignada (otro caso o este caso)")
        return
    if cod not in ok:
        ok.append(cod)


# ─────────────────────────────────────────────────────────────────────────────
# Persistencia BD
# ─────────────────────────────────────────────────────────────────────────────


def _tabla_biblioteca_precio_existe() -> bool:
    df = get_dataframe(
        "SELECT to_regclass('public.biblioteca_precio')::text AS t"
    )
    return bool(df is not None and not df.empty and df.iloc[0]["t"])


def listar_bibliotecas(proveedor_id: int) -> pd.DataFrame:
    if not _tabla_biblioteca_precio_existe():
        return pd.DataFrame()
    df = get_dataframe(
        """SELECT id, nombre, descripcion, created_at, updated_at
           FROM biblioteca_precio
           WHERE proveedor_id = :pid AND activo = true
           ORDER BY nombre""",
        {"pid": proveedor_id},
    )
    return df if df is not None else pd.DataFrame()


def mensaje_si_falta_migracion_biblioteca() -> str | None:
    if _tabla_biblioteca_precio_existe():
        return None
    return (
        "Falta la migración del maestro de bibliotecas. "
        "Ejecutá: `python scripts/run_migration_044.py` y reiniciá Streamlit."
    )


def actualizar_nombre_biblioteca(
    biblioteca_id: int,
    nombre: str,
) -> tuple[bool, str]:
    """Renombra la biblioteca en biblioteca_precio."""
    nom = str(nombre or "").strip()
    if not nom:
        return False, "El nombre de la biblioteca es obligatorio."
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """UPDATE biblioteca_precio
                       SET nombre = :nom, updated_at = now()
                       WHERE id = :bid"""
                ),
                {"nom": nom, "bid": int(biblioteca_id)},
            )
        return True, ""
    except Exception as e:
        DBInspector.log(f"[BIB] actualizar_nombre: {e}", "ERROR")
        return False, str(e)


def crear_biblioteca(
    proveedor_id: int, nombre: str, descripcion: str = ""
) -> tuple[int | None, str]:
    msg = mensaje_si_falta_migracion_biblioteca()
    if msg:
        return None, msg
    nom = nombre.strip()
    if not nom:
        return None, "El nombre de la biblioteca es obligatorio."
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """INSERT INTO biblioteca_precio (proveedor_id, nombre, descripcion)
                       VALUES (:pid, :nom, :desc)
                       ON CONFLICT (proveedor_id, nombre) DO UPDATE
                           SET activo = true, updated_at = now()
                       RETURNING id"""
                ),
                {"pid": proveedor_id, "nom": nom, "desc": descripcion or None},
            ).fetchone()
            if row:
                return int(row[0]), ""
            return None, "No se obtuvo id al crear la biblioteca."
    except Exception as e:
        DBInspector.log(f"[BIB] crear_biblioteca: {e}", "ERROR")
        return None, str(e)


def cargar_pilar_datos(
    proveedor_id: int,
    *,
    usar_cache: bool = True,
) -> tuple[list[str], dict[str, int | None], dict[int, str], bool]:
    """
    Pilar de líneas con FK marca (linea.marca_id → marca_v2).

    Returns:
        codigos, codigo→marca_id, marca_id→descp_marca, hay_lineas_sin_marca
    """
    if usar_cache:
        try:
            import streamlit as st

            key = f"_cache_pilar_datos_{proveedor_id}"
            if key in st.session_state:
                return st.session_state[key]
        except Exception:
            pass

    df = get_dataframe(
        """SELECT l.codigo_proveedor::text AS cod,
                  l.marca_id,
                  mv.descp_marca::text AS marca
           FROM linea l
           LEFT JOIN marca_v2 mv ON mv.id_marca = l.marca_id
           WHERE l.proveedor_id = :pid AND l.activo = true
           ORDER BY l.codigo_proveedor::bigint""",
        {"pid": proveedor_id},
    )
    codigos: list[str] = []
    cod_marca: dict[str, int | None] = {}
    catalogo: dict[int, str] = {}
    sin_marca = False

    if df is not None and not df.empty:
        for _, r in df.iterrows():
            try:
                cod = str(int(float(str(r["cod"]))))
            except (ValueError, TypeError):
                continue
            codigos.append(cod)
            raw_mid = r.get("marca_id")
            if raw_mid is None or (isinstance(raw_mid, float) and pd.isna(raw_mid)):
                cod_marca[cod] = None
                sin_marca = True
            else:
                mid = int(raw_mid)
                cod_marca[cod] = mid
                nom = r.get("marca")
                if nom is not None and str(nom).strip():
                    catalogo[mid] = str(nom).strip()

    if not catalogo:
        catalogo = cargar_catalogo_marcas_pilar(proveedor_id)

    result = (codigos, cod_marca, catalogo, sin_marca)
    if usar_cache:
        try:
            import streamlit as st

            st.session_state[f"_cache_pilar_datos_{proveedor_id}"] = result
            st.session_state[f"_cache_pilar_cod_{proveedor_id}"] = codigos
        except Exception:
            pass
    return result


def cargar_catalogo_marcas_pilar(proveedor_id: int) -> dict[int, str]:
    """Marcas distintas del pilar (linea.marca_id → marca_v2)."""
    df = get_dataframe(
        """SELECT DISTINCT mv.id_marca AS marca_id,
                  mv.descp_marca::text AS marca
           FROM linea l
           INNER JOIN marca_v2 mv ON mv.id_marca = l.marca_id
           WHERE l.proveedor_id = :pid AND l.activo = true
             AND mv.descp_marca IS NOT NULL
           ORDER BY mv.descp_marca""",
        {"pid": proveedor_id},
    )
    out: dict[int, str] = {}
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        try:
            mid = int(r["marca_id"])
        except (ValueError, TypeError):
            continue
        nom = str(r.get("marca") or "").strip()
        if nom:
            out[mid] = nom
    return out


def cargar_pilar_lineas(proveedor_id: int, *, usar_cache: bool = True) -> list[str]:
    codigos, _, _, _ = cargar_pilar_datos(proveedor_id, usar_cache=usar_cache)
    return codigos


def _lineas_por_caso_biblioteca(biblioteca_id: int) -> dict[int, list[str]]:
    if not _tabla_biblioteca_precio_existe():
        return {}
    df = get_dataframe(
        """SELECT bcl.caso_biblioteca_id, l.codigo_proveedor::text AS cod
           FROM biblioteca_caso_linea bcl
           JOIN linea l ON l.id = bcl.linea_id
           WHERE bcl.biblioteca_id = :bid
           ORDER BY bcl.caso_biblioteca_id, l.codigo_proveedor""",
        {"bid": biblioteca_id},
    )
    out: dict[int, list[str]] = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        cid = int(row["caso_biblioteca_id"])
        try:
            cod = str(int(float(str(row["cod"]))))
        except (ValueError, TypeError):
            continue
        out.setdefault(cid, []).append(cod)
    return out


def plantilla_casos_desde_biblioteca(
    proveedor_id: int,
    biblioteca_id: int,
) -> list[dict]:
    """Casos + líneas de una biblioteca, listos para re_plantilla_casos / Paso 2."""
    state = cargar_biblioteca_editor_state(proveedor_id, biblioteca_id)
    if not state:
        return []
    out: list[dict] = []
    for _clave, data in state.casos.items():
        rec = {
            k: v
            for k, v in data.items()
            if k not in ("caso_biblioteca_id",)
        }
        lineas = rec.get("lineas") or set()
        if isinstance(lineas, set):
            rec["lineas"] = sorted(
                lineas,
                key=lambda x: (len(x), int(x) if str(x).isdigit() else x),
            )
        out.append(rec)
    return out


def cargar_biblioteca_editor_state(
    proveedor_id: int,
    biblioteca_id: int,
) -> BibliotecaEditorState | None:
    if not _tabla_biblioteca_precio_existe():
        return None
    meta = get_dataframe(
        """SELECT id, nombre FROM biblioteca_precio
           WHERE id = :bid AND proveedor_id = :pid AND activo = true""",
        {"bid": biblioteca_id, "pid": proveedor_id},
    )
    if meta is None or meta.empty:
        return None

    lineas_map = _lineas_por_caso_biblioteca(biblioteca_id)
    df_casos = get_dataframe(
        """SELECT id, nombre_caso, dolar_politica, factor_conversion,
                  descuento_1, descuento_2, descuento_3, descuento_4,
                  genera_lpc03_lpc04, alcance_tipo, marcas, lineas
           FROM caso_precio_biblioteca
           WHERE biblioteca_id = :bid AND activo = true
           ORDER BY nombre_caso""",
        {"bid": biblioteca_id},
    )

    codigos, cod_marca, marcas, sin_marca = cargar_pilar_datos(proveedor_id)
    state = BibliotecaEditorState(
        proveedor_id=proveedor_id,
        biblioteca_id=biblioteca_id,
        nombre=str(meta.iloc[0]["nombre"]),
        pilar_lineas=codigos,
        pilar_marca_por_codigo=cod_marca,
        pilar_marcas=marcas,
        pilar_tiene_sin_marca=sin_marca,
    )

    if df_casos is not None and not df_casos.empty:
        for _, row in df_casos.iterrows():
            cid = int(row["id"])
            rec = row.to_dict()
            rec["caso_biblioteca_id"] = cid
            codes = lineas_map.get(cid) or parse_lineas_array(rec.get("lineas"))
            rec["lineas"] = set(codes)
            clave = state.ensure_caso(str(rec["nombre_caso"]), rec)
            state.casos[clave].update(rec)
            state.casos[clave]["lineas"] = set(codes)
    return state


def persistir_un_caso_biblioteca(
    state: BibliotecaEditorState,
    caso_key: str,
) -> tuple[int | None, str]:
    """
    Persiste un caso comercial en BD (caso_precio_biblioteca + biblioteca_caso_linea).
    Usar al crear/editar un caso sin esperar al guardado global de la biblioteca.
    """
    if not state.biblioteca_id:
        return None, "Biblioteca sin ID. Creala desde el catálogo y volvé a abrir el editor."
    data = state.casos.get(caso_key)
    if not data:
        return None, "El caso no existe en el editor."

    conflictos = state.validar_exclusividad_global()
    if conflictos:
        return None, "Exclusividad: " + "; ".join(conflictos[:3])

    bid = int(state.biblioteca_id)
    norm = normalizar_caso_evento(data)
    payload = _caso_dict_para_db(norm)
    nombre = norm["nombre_caso"]
    uk = nombre.strip().upper()
    lineas_set = data.get("lineas") or set()
    if isinstance(lineas_set, list):
        lineas_set = set(lineas_set)

    lineas_list = parse_lineas_array(lineas_set)
    alcance = "lineas" if lineas_list else (
        "marcas" if norm.get("marcas") else "lineas"
    )

    try:
        with engine.begin() as conn:
            caso_id = _upsert_caso_biblioteca_en_conn(
                conn,
                state.proveedor_id,
                bid,
                payload,
                alcance_tipo=alcance,
                lineas_list=lineas_list,
            )
            if not caso_id:
                return None, "No se pudo guardar el caso en la biblioteca."

            _persistir_lineas_caso_biblioteca(
                bid, caso_id, state.proveedor_id, lineas_set
            )
            state.casos[caso_key]["caso_biblioteca_id"] = caso_id
            state.casos[caso_key]["lineas"] = set(lineas_set)
            state.dirty = False
            return caso_id, ""
    except Exception as e:
        err = str(e)
        if "biblioteca_id" in err and "does not exist" in err:
            return None, (
                "Falta la migración 044 (columna biblioteca_id). "
                "Ejecutá: python scripts/run_migration_044.py"
            )
        if "biblioteca_caso_linea" in err and "does not exist" in err:
            return None, (
                "Falta la tabla biblioteca_caso_linea. "
                "Ejecutá: python scripts/run_migration_044.py"
            )
        if "caso_precio_biblioteca_proveedor_id_nombre_caso" in err:
            try:
                with engine.begin() as conn:
                    caso_id = _id_caso_biblioteca_por_nombre(
                        conn, state.proveedor_id, nombre, bid
                    )
                    if caso_id:
                        _persistir_lineas_caso_biblioteca(
                            bid, caso_id, state.proveedor_id, lineas_set
                        )
                        state.casos[caso_key]["caso_biblioteca_id"] = caso_id
                        state.casos[caso_key]["lineas"] = set(lineas_set)
                        state.dirty = False
                        return caso_id, ""
            except Exception:
                pass
        DBInspector.log(f"[BIB] persistir_un_caso: {e}", "ERROR")
        return None, err


def _id_caso_biblioteca_por_nombre(
    conn,
    proveedor_id: int,
    nombre_caso: str,
    biblioteca_id: int | None = None,
) -> int | None:
    """Busca caso por (proveedor, nombre). Prioriza la biblioteca actual."""
    uk = nombre_caso.strip().upper()
    if biblioteca_id is not None:
        row = conn.execute(
            text(
                """SELECT id FROM caso_precio_biblioteca
                   WHERE proveedor_id = :pid
                     AND biblioteca_id = :bid
                     AND upper(btrim(nombre_caso)) = :uk
                   ORDER BY activo DESC, id DESC
                   LIMIT 1"""
            ),
            {"pid": proveedor_id, "bid": biblioteca_id, "uk": uk},
        ).fetchone()
        if row:
            return int(row[0])
    row = conn.execute(
        text(
            """SELECT id FROM caso_precio_biblioteca
               WHERE proveedor_id = :pid
                 AND upper(btrim(nombre_caso)) = :uk
               ORDER BY activo DESC, id DESC
               LIMIT 1"""
        ),
        {"pid": proveedor_id, "uk": uk},
    ).fetchone()
    return int(row[0]) if row else None


def _upsert_caso_biblioteca_en_conn(
    conn,
    proveedor_id: int,
    biblioteca_id: int,
    payload: dict,
    *,
    alcance_tipo: str,
    lineas_list: list,
) -> int | None:
    """
    Inserta o actualiza caso_precio_biblioteca (UNIQUE proveedor_id + nombre_caso).
    No falla si el nombre ya existe en otra biblioteca del mismo proveedor.
    """
    row = conn.execute(
        text(
            """INSERT INTO caso_precio_biblioteca
                   (proveedor_id, biblioteca_id, nombre_caso,
                    dolar_politica, factor_conversion,
                    descuento_1, descuento_2, descuento_3, descuento_4,
                    genera_lpc03_lpc04, alcance_tipo, marcas, lineas, activo)
               VALUES (:pid, :bid, :nc, :dp, :fc, :d1, :d2, :d3, :d4,
                       :glpc, :at, :marcas, :lineas, true)
               ON CONFLICT (proveedor_id, nombre_caso) DO UPDATE SET
                    biblioteca_id = EXCLUDED.biblioteca_id,
                    nombre_caso = EXCLUDED.nombre_caso,
                    dolar_politica = EXCLUDED.dolar_politica,
                    factor_conversion = EXCLUDED.factor_conversion,
                    descuento_1 = EXCLUDED.descuento_1,
                    descuento_2 = EXCLUDED.descuento_2,
                    descuento_3 = EXCLUDED.descuento_3,
                    descuento_4 = EXCLUDED.descuento_4,
                    genera_lpc03_lpc04 = EXCLUDED.genera_lpc03_lpc04,
                    alcance_tipo = EXCLUDED.alcance_tipo,
                    marcas = EXCLUDED.marcas,
                    lineas = EXCLUDED.lineas,
                    activo = true
               RETURNING id"""
        ),
        {
            "pid": proveedor_id,
            "bid": biblioteca_id,
            "nc": payload["nombre_caso"],
            "dp": payload["dolar_politica"],
            "fc": payload["factor_conversion"],
            "d1": payload["descuento_1"],
            "d2": payload["descuento_2"],
            "d3": payload["descuento_3"],
            "d4": payload["descuento_4"],
            "glpc": payload["genera_lpc03_lpc04"],
            "at": alcance_tipo,
            "marcas": payload["marcas"],
            "lineas": lineas_list,
        },
    ).fetchone()
    return int(row[0]) if row else None


def _codigos_proveedor_a_int(codigos: list[str]) -> list[int]:
    out: list[int] = []
    for c in codigos:
        try:
            out.append(int(float(str(c).strip())))
        except (ValueError, TypeError):
            continue
    return out


def quitar_lineas_de_caso_biblioteca(
    biblioteca_id: int,
    caso_biblioteca_id: int,
    proveedor_id: int,
    codigos_quitar: list[str],
    lineas_restantes: set[str] | list[str],
) -> tuple[bool, str]:
    """DELETE incremental (rápido) — no reescribe las 1.000+ líneas del caso."""
    codes_del = _codigos_proveedor_a_int(codigos_quitar)
    if not codes_del:
        return True, ""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """DELETE FROM biblioteca_caso_linea bcl
                       USING linea l
                       WHERE bcl.linea_id = l.id
                         AND bcl.biblioteca_id = :bid
                         AND bcl.caso_biblioteca_id = :cid
                         AND l.proveedor_id = :pid
                         AND l.codigo_proveedor = ANY(:codes)"""
                ),
                {
                    "bid": biblioteca_id,
                    "cid": caso_biblioteca_id,
                    "pid": proveedor_id,
                    "codes": codes_del,
                },
            )
            conn.execute(
                text(
                    "UPDATE caso_precio_biblioteca SET lineas = :lin WHERE id = :cid"
                ),
                {
                    "lin": parse_lineas_array(list(lineas_restantes)),
                    "cid": caso_biblioteca_id,
                },
            )
        return True, ""
    except Exception as e:
        DBInspector.log(f"[BIB] quitar_lineas: {e}", "ERROR")
        return False, str(e)


def vaciar_lineas_caso_biblioteca(
    biblioteca_id: int,
    caso_biblioteca_id: int,
) -> tuple[bool, str]:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM biblioteca_caso_linea "
                    "WHERE biblioteca_id = :bid AND caso_biblioteca_id = :cid"
                ),
                {"bid": biblioteca_id, "cid": caso_biblioteca_id},
            )
            conn.execute(
                text(
                    "UPDATE caso_precio_biblioteca SET lineas = :lin WHERE id = :cid"
                ),
                {"lin": [], "cid": caso_biblioteca_id},
            )
        return True, ""
    except Exception as e:
        return False, str(e)


def agregar_lineas_de_caso_biblioteca(
    biblioteca_id: int,
    caso_biblioteca_id: int,
    proveedor_id: int,
    codigos_agregar: list[str],
    lineas_finales: set[str] | list[str],
) -> tuple[bool, str]:
    """INSERT incremental de líneas nuevas en el caso."""
    codes_add = _codigos_proveedor_a_int(codigos_agregar)
    if not codes_add:
        return True, ""
    try:
        with engine.begin() as conn:
            conflict = _fragment_on_conflict_lineas(conn)
            conn.execute(
                text(
                    f"""INSERT INTO biblioteca_caso_linea
                           (biblioteca_id, caso_biblioteca_id, linea_id)
                       SELECT :bid, :cid, l.id
                       FROM linea l
                       WHERE l.proveedor_id = :pid
                         AND l.codigo_proveedor = ANY(:codes)
                       {conflict}"""
                ),
                {
                    "bid": biblioteca_id,
                    "cid": caso_biblioteca_id,
                    "pid": proveedor_id,
                    "codes": codes_add,
                },
            )
            conn.execute(
                text(
                    "UPDATE caso_precio_biblioteca SET lineas = :lin WHERE id = :cid"
                ),
                {
                    "lin": parse_lineas_array(lineas_finales),
                    "cid": caso_biblioteca_id,
                },
            )
        return True, ""
    except Exception as e:
        DBInspector.log(f"[BIB] agregar_lineas: {e}", "ERROR")
        return False, str(e)


def sincronizar_lineas_caso_en_bd(
    state: BibliotecaEditorState,
    caso_key: str,
    *,
    codigos_quitar: list[str] | None = None,
    codigos_agregar: list[str] | None = None,
    vaciar: bool = False,
) -> tuple[bool, str]:
    """Persiste solo el delta de líneas (quitar / agregar / vaciar)."""
    data = state.casos.get(caso_key)
    if not data:
        return False, "Caso no encontrado."
    caso_id = data.get("caso_biblioteca_id")
    bid = state.biblioteca_id
    if not bid or not caso_id:
        return True, ""
    lineas = data.get("lineas") or set()
    if isinstance(lineas, list):
        lineas = set(lineas)
    if vaciar:
        return vaciar_lineas_caso_biblioteca(int(bid), int(caso_id))
    if codigos_quitar:
        ok, err = quitar_lineas_de_caso_biblioteca(
            int(bid),
            int(caso_id),
            state.proveedor_id,
            codigos_quitar,
            lineas,
        )
        if not ok:
            return ok, err
    if codigos_agregar:
        return agregar_lineas_de_caso_biblioteca(
            int(bid),
            int(caso_id),
            state.proveedor_id,
            codigos_agregar,
            lineas,
        )
    return True, ""


def _fragment_on_conflict_lineas(conn) -> str:
    """Compatibilidad migración 044/045/046."""
    row = conn.execute(
        text(
            """SELECT 1 FROM pg_constraint
               WHERE conname = 'biblioteca_caso_linea_bib_linea_uq' LIMIT 1"""
        )
    ).fetchone()
    if row:
        return "ON CONFLICT (biblioteca_id, linea_id) DO NOTHING"
    return "ON CONFLICT (caso_biblioteca_id, linea_id) DO NOTHING"


def _persistir_lineas_caso_biblioteca(
    biblioteca_id: int,
    caso_biblioteca_id: int,
    proveedor_id: int,
    codigos: set[str] | list[str],
    conn=None,
) -> int:
    """Reemplaza líneas FK de un caso dentro de la biblioteca."""
    codes = parse_lineas_array(codigos)
    conflict = "ON CONFLICT (caso_biblioteca_id, linea_id) DO NOTHING"

    def _run(connection) -> int:
        nonlocal conflict
        conflict = _fragment_on_conflict_lineas(connection)
        connection.execute(
            text(
                "DELETE FROM biblioteca_caso_linea "
                "WHERE biblioteca_id = :bid AND caso_biblioteca_id = :cid"
            ),
            {"bid": biblioteca_id, "cid": caso_biblioteca_id},
        )
        n = 0
        if codes:
            codes_int = _codigos_proveedor_a_int(codes)
            if codes_int:
                r = connection.execute(
                    text(
                        f"""INSERT INTO biblioteca_caso_linea
                               (biblioteca_id, caso_biblioteca_id, linea_id)
                           SELECT :bid, :cid, l.id
                           FROM linea l
                           WHERE l.proveedor_id = :pid
                             AND l.codigo_proveedor = ANY(:codes)
                           {conflict}
                           RETURNING id"""
                    ),
                    {
                        "bid": biblioteca_id,
                        "cid": caso_biblioteca_id,
                        "pid": proveedor_id,
                        "codes": codes_int,
                    },
                )
                n = len(r.fetchall())
        connection.execute(
            text(
                "UPDATE caso_precio_biblioteca SET lineas = :lin WHERE id = :cid"
            ),
            {"lin": codes, "cid": caso_biblioteca_id},
        )
        return n

    try:
        if conn is not None:
            return _run(conn)
        with engine.begin() as c:
            return _run(c)
    except Exception as e:
        DBInspector.log(f"[BIB] persistir_lineas: {e}", "ERROR")
        raise


def recargar_lineas_caso_desde_bd(
    state: BibliotecaEditorState,
    caso_key: str,
) -> set[str]:
    """Sincroniza state.casos[].lineas con biblioteca_caso_linea en BD."""
    data = state.casos.get(caso_key)
    if not data or not state.biblioteca_id:
        return set()
    cid = data.get("caso_biblioteca_id")
    if not cid:
        ln = data.get("lineas") or set()
        return set(ln) if isinstance(ln, set) else set(ln)
    m = _lineas_por_caso_biblioteca(int(state.biblioteca_id))
    codes = set(m.get(int(cid), []))
    data["lineas"] = codes
    return codes


def guardar_lineas_caso_directo(
    state: BibliotecaEditorState,
    caso_key: str,
) -> tuple[int, str]:
    """
    Reemplazo atómico del contenedor de líneas en BD (DELETE + INSERT masivo).
    Usar tras editar la lista en texto; no reescribe parámetros del caso.
    """
    if not state.biblioteca_id:
        return 0, "Biblioteca sin ID."
    data = state.casos.get(caso_key)
    if not data:
        return 0, "Caso no encontrado."
    caso_id = data.get("caso_biblioteca_id")
    if not caso_id:
        return 0, "El caso aún no está en BD. Usá «Crear caso» o «Guardar biblioteca»."
    lineas = data.get("lineas") or set()
    if isinstance(lineas, list):
        lineas = set(lineas)
    conflictos = state.validar_exclusividad_global()
    if conflictos:
        return 0, "Exclusividad: " + "; ".join(conflictos[:3])
    try:
        esperado = len(lineas)
        _persistir_lineas_caso_biblioteca(
            int(state.biblioteca_id),
            int(caso_id),
            state.proveedor_id,
            lineas,
        )
        en_bd = recargar_lineas_caso_desde_bd(state, caso_key)
        if len(en_bd) != esperado:
            return len(en_bd), (
                f"Guardado incompleto: quedaron {len(en_bd):,} línea(s) en BD "
                f"(esperabas {esperado:,}). Revisá códigos que no existen en el pilar."
            )
        return len(en_bd), ""
    except Exception as e:
        return 0, str(e)


def guardar_estado_biblioteca(
    state: BibliotecaEditorState,
    *,
    modo: str,
    nuevo_nombre: str | None = None,
) -> tuple[int | None, str]:
    """
    Persiste el editor.
    modo: 'sustituir' | 'nueva'
    Retorna (biblioteca_id, error).
    """
    conflictos = state.validar_exclusividad_global()
    if conflictos:
        return None, "Exclusividad: " + "; ".join(conflictos[:5])

    bid = state.biblioteca_id
    if modo == "nueva":
        nombre = (nuevo_nombre or "").strip()
        if not nombre:
            return None, "Indicá el nombre de la nueva biblioteca."
        bid, err_crear = crear_biblioteca(state.proveedor_id, nombre)
        if err_crear:
            return None, err_crear
        if not bid:
            return None, "No se pudo crear la biblioteca."
        state.biblioteca_id = bid
        state.nombre = nombre
    elif not bid:
        return None, "Biblioteca sin ID."

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """UPDATE biblioteca_precio
                       SET nombre = :nom, updated_at = now()
                       WHERE id = :bid"""
                ),
                {"bid": bid, "nom": (state.nombre or "").strip()},
            )
            existentes = conn.execute(
                text(
                    "SELECT id, nombre_caso FROM caso_precio_biblioteca "
                    "WHERE biblioteca_id = :bid AND activo = true"
                ),
                {"bid": bid},
            ).fetchall()
            exist_map = {str(r[1]).strip().upper(): int(r[0]) for r in existentes}
            vistos: set[str] = set()

            for _clave, data in state.casos.items():
                lineas_set = data.get("lineas") or set()
                if isinstance(lineas_set, list):
                    lineas_set = set(lineas_set)
                lineas_list = parse_lineas_array(lineas_set)

                norm = normalizar_caso_evento({**data, "lineas": lineas_list})
                nombre = norm["nombre_caso"]
                uk = nombre.strip().upper()
                vistos.add(uk)
                payload = _caso_dict_para_db(norm)
                at_lineas = "lineas" if lineas_list else (
                    "marcas" if norm.get("marcas") else "lineas"
                )
                caso_id = _upsert_caso_biblioteca_en_conn(
                    conn,
                    state.proveedor_id,
                    int(bid),
                    payload,
                    alcance_tipo=at_lineas,
                    lineas_list=lineas_list,
                )

                if caso_id:
                    _persistir_lineas_caso_biblioteca(
                        bid,
                        caso_id,
                        state.proveedor_id,
                        lineas_set,
                        conn=conn,
                    )

            for uk, cid in exist_map.items():
                if uk not in vistos:
                    conn.execute(
                        text("DELETE FROM biblioteca_caso_linea WHERE caso_biblioteca_id = :cid"),
                        {"cid": cid},
                    )
                    conn.execute(
                        text(
                            "UPDATE caso_precio_biblioteca SET activo = false WHERE id = :cid"
                        ),
                        {"cid": cid},
                    )

        state.dirty = False
        return bid, ""
    except Exception as e:
        DBInspector.log(f"[BIB] guardar_estado: {e}", "ERROR")
        return None, str(e)


def duplicar_biblioteca(
    proveedor_id: int,
    biblioteca_id: int,
    nuevo_nombre: str,
) -> tuple[int | None, str]:
    src = cargar_biblioteca_editor_state(proveedor_id, biblioteca_id)
    if not src:
        return None, "Biblioteca origen no encontrada."
    copia = deepcopy(src)
    copia.biblioteca_id = None
    copia.nombre = nuevo_nombre.strip()
    return guardar_estado_biblioteca(copia, modo="nueva", nuevo_nombre=nuevo_nombre)


def vincular_biblioteca_a_evento(evento_id: int, biblioteca_id: int | None) -> bool:
    if biblioteca_id is None:
        return True
    return commit_query(
        "UPDATE precio_evento SET biblioteca_precio_id = :bid WHERE id = :eid",
        {"bid": biblioteca_id, "eid": evento_id},
    )


def aplicar_biblioteca_a_evento(
    evento_id: int,
    proveedor_id: int,
    biblioteca_id: int,
    *,
    reemplazar_matriz: bool = True,
) -> tuple[bool, str, int]:
    """
    Copia casos + contenedor de líneas de la biblioteca al listado (precio_evento).
  """
    state = cargar_biblioteca_editor_state(proveedor_id, biblioteca_id)
    if not state:
        return False, "No se pudo cargar la biblioteca.", 0

    conflictos = state.validar_exclusividad_global()
    if conflictos:
        return False, "Biblioteca inconsistente: " + conflictos[0], 0

    if reemplazar_matriz:
        ok, msg = vaciar_matriz_evento(evento_id)
        if not ok and msg:
            return False, msg, 0

    n_casos = 0
    for caso_norm in state.to_casos_normalizados():
        _, err = persistir_caso_matriz_evento(evento_id, proveedor_id, caso_norm)
        if err:
            return False, err, n_casos
        n_casos += 1

    vincular_biblioteca_a_evento(evento_id, biblioteca_id)
    return True, "", n_casos


def crear_caso_en_biblioteca_vacia(
    proveedor_id: int,
    biblioteca_id: int,
    nombre_caso: str,
    params: dict | None = None,
) -> tuple[int | None, str]:
    """Añade un caso vacío a la biblioteca (para UI acordeón)."""
    norm = normalizar_caso_evento(params or {})
    norm["nombre_caso"] = nombre_caso.strip()
    payload = _caso_dict_para_db(norm)
    try:
        with engine.begin() as conn:
            cid = _upsert_caso_biblioteca_en_conn(
                conn,
                proveedor_id,
                biblioteca_id,
                payload,
                alcance_tipo="lineas",
                lineas_list=[],
            )
            return (cid, "") if cid else (None, "Error al crear caso.")
    except Exception as e:
        return None, str(e)
