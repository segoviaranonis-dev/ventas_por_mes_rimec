# Checklist auditoría Auto — OT-DEPOSITO-WEB-510-001

> Usar **después** de que Claude Code entregue evidencia. Auto (Maestro) ejecuta o revisa.

---

## 1. Diccionario Web (`caso_precio_web_regla`)

```sql
SELECT caso_codigo, markup_pct, activo, updated_at
FROM caso_precio_web_regla
ORDER BY caso_codigo;
```

| Check | Esperado |
|-------|----------|
| 6 filas activas | 5 casos + DEFAULT |
| BR-VZ / ACT-BRSPORT | 50% |
| CARTERAS / CHINELO / PROMOCIONAL | 40% |

---

## 2. Función precio (sanity)

```sql
SELECT fn_precio_venta_web(82500, 'ACT-BRSPORT') AS pv;  -- esperado 124000 si +50% centena
SELECT fn_precio_venta_web(100000, 'BR-VZ-MD-ML-MKA-O') AS pv;  -- 150000
```

---

## 3. Paridad Depósito ↔ Web

```powershell
python scripts/auditar_paridad_deposito_web_rimec.py
```

| Resultado | PASS |
|-----------|------|
| MISMATCH = 0 en moléculas con stock Depósito Web | |
| MISSING_LPN = 0 para ACTVITTA 4 artículos | |

---

## 4. UI Nexus — Depósito Web

- [ ] Columnas: Línea, Ref., Material, Color, **LPN**, **Caso**, **Markup %**, **Precio venta**, Stock  
- [ ] ACTVITTA 4 artículos, 44 pares (stock sin regresión)  
- [ ] Precio venta ≠ LPN cuando markup > 0  

---

## 5. UI rimec-web

- [ ] Lista 1 (Bazar): precio mostrado = **Precio venta** del paso 4 para el mismo SKU  
- [ ] Carrito: subtotal usa `precio_web` (sesionVenta)  

---

## 6. Prueba regresión diccionario

1. Nexus → Diccionario Web → CHINELO 40% → **45%**  
2. Refresh Depósito Web + Bazar  
3. SKU caso CHINELO (si hay stock): precio sube ~3.5% vs antes  

---

## Veredicto

| | |
|-|-|
| **PASS** | C1–C4 evidencia + checklist completo |
| **FAIL** | Pegar `OT-DEPOSITO-WEB-510-001-EVIDENCIA.json` + mismatch rows |
