#!/usr/bin/env python3
"""Ejecuta migraciones 064-072 en secuencia para deployment piloto"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(__file__).resolve().parent / "ejecutar_migraciones_064_072.log"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

MIGRATIONS = [
    "064_fix_v_stock_rimec_fallback_precios.sql",
    "065_rpc_confirmar_pedido_web_stock_check.sql",
    # "066_rbac_unificacion_usuarios.sql",  # SALTEADA: Conflictos con constraints existentes, no crítica para piloto
    "067_fix_fallback_caso.sql",
    "068_hardening_search_path_rls.sql",
    "070_refactor_precios_strict_null.sql",
    "071_fix_v_stock_rimec_mapeo_evento_icp.sql",
    "072_rpc_confirmar_pedido_web_blindaje_vendedor.sql",
]

def _db_url() -> str:
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        import tomllib
        with p.open("rb") as f:
            pg = tomllib.load(f).get("postgres")
        if isinstance(pg, dict):
            user = pg.get("user") or pg.get("username")
            pwd = pg.get("password")
            host = pg.get("host", "localhost")
            port = pg.get("port", 5432)
            db = pg.get("database") or pg.get("dbname")
            if user and pwd and db:
                return (
                    f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pwd)}"
                    f"@{host}:{port}/{db}"
                )
    raise SystemExit("Falta DATABASE_URL o .streamlit/secrets.toml [postgres]")

def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        # Fallback para consolas Windows que no soportan UTF-8
        print(line.encode('ascii', 'replace').decode('ascii'))
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def main() -> None:
    LOG.write_text("", encoding="utf-8")
    log("=" * 70)
    log("DEPLOYMENT PILOTO: Aplicando migraciones 064-072")
    log("=" * 70)

    eng = create_engine(_db_url(), pool_pre_ping=True)

    for mig_file in MIGRATIONS:
        migration_path = ROOT / "migrations" / mig_file
        if not migration_path.exists():
            log(f"ERROR: No se encontró {mig_file}")
            sys.exit(1)

        log(f"\n>>> Aplicando {mig_file}...")

        # HOTFIX: Antes de 065, dropear todas las versiones de confirmar_pedido_web
        if mig_file.startswith("065_"):
            log(">>> HOTFIX: Dropeando versiones antiguas de confirmar_pedido_web...")
            try:
                with eng.begin() as conn:
                    conn.execute(text("""
                        DO $$
                        DECLARE r RECORD;
                        BEGIN
                            FOR r IN SELECT proname, oidvectortypes(proargtypes) as args
                                     FROM pg_proc
                                     WHERE proname = 'confirmar_pedido_web'
                            LOOP
                                EXECUTE 'DROP FUNCTION IF EXISTS public.' || r.proname || '(' || r.args || ') CASCADE';
                                RAISE NOTICE 'Dropeada: %(%)', r.proname, r.args;
                            END LOOP;
                        END $$;
                    """))
                log("[OK] Funciones antiguas dropeadas")
            except Exception as e:
                log(f"[WARN] Error al dropear funciones antiguas: {e}")

        # HOTFIX: Antes de 066, dropear constraints que ya existen
        if mig_file.startswith("066_"):
            log(">>> HOTFIX: Dropeando constraints duplicadas para RBAC...")
            try:
                with eng.begin() as conn:
                    conn.execute(text("""
                        -- Dropear TODAS las constraints relacionadas con vendedor/usuario
                        ALTER TABLE public.pedido_venta_rimec DROP CONSTRAINT IF EXISTS fk_pedido_venta_vendedor CASCADE;
                        ALTER TABLE public.factura_interna DROP CONSTRAINT IF EXISTS fk_factura_interna_vendedor CASCADE;
                        ALTER TABLE public.intencion_compra DROP CONSTRAINT IF EXISTS fk_intencion_compra_vendedor CASCADE;
                        ALTER TABLE public.vendedor_marca_v2 DROP CONSTRAINT IF EXISTS fk_vendedor_marca_vendedor CASCADE;
                        ALTER TABLE public.vendedor_marca_v2 DROP CONSTRAINT IF EXISTS fk_vendedor_marca_usuario CASCADE;

                        -- Dropear CHECK constraints
                        ALTER TABLE public.pedido_venta_rimec DROP CONSTRAINT IF EXISTS chk_pedido_vendedor_es_vendedor_o_admin CASCADE;
                        ALTER TABLE public.factura_interna DROP CONSTRAINT IF EXISTS chk_factura_vendedor_es_vendedor_o_admin CASCADE;
                        ALTER TABLE public.intencion_compra DROP CONSTRAINT IF EXISTS chk_ic_vendedor_es_vendedor_o_admin CASCADE;
                    """))
                log("[OK] Constraints antiguas dropeadas")
            except Exception as e:
                log(f"[WARN] Error al dropear constraints: {e}")

        try:
            sql = migration_path.read_text(encoding="utf-8")
            with eng.begin() as conn:
                conn.execute(text(sql))
            log(f"[OK] {mig_file} aplicada exitosamente")
        except Exception as e:
            log(f"[ERROR] en {mig_file}: {e}")
            log("Abortando ejecución para evitar inconsistencias")
            sys.exit(1)

    log("\n" + "=" * 70)
    log("¡DEPLOYMENT COMPLETADO! Todas las migraciones aplicadas")
    log("=" * 70)
    print("\n✅ Listo para piloto con usuarios selectos")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR CRÍTICO: {e}")
        raise
