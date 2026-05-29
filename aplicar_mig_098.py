#!/usr/bin/env python3
"""Aplicar migración 098 - Agregar quincena a v_stock_rimec"""
from core.database import engine
from sqlalchemy import text as sqlt

print("Aplicando migración 098...")

sql = open('migrations/098_agregar_quincena_a_v_stock_rimec.sql', encoding='utf-8').read()

with engine.begin() as conn:
    conn.execute(sqlt(sql))
    print("OK - Vista v_stock_rimec actualizada")
    print("OK - Columnas agregadas: quincena_arribo_id, quincena_desc")
    print("OK - RIMEC Web ahora puede leer el dato duro")
