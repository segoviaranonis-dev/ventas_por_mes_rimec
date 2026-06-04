def talla_sort_key(talla_key: str) -> tuple[int, str]:
    raw = str(talla_key).strip().lower().removeprefix("t")
    try:
        return (int(raw), str(talla_key))
    except ValueError:
        return (9999, str(talla_key))


def normalizar_tallas_a_pares(tallas: dict, pares_objetivo) -> dict[str, int]:
    """
    Escala una curva base de tallas para que sume exactamente `pares_objetivo`.

    Caso real: `ppd.grades_json` suele representar UNA caja. Si la FI factura
    3 cajas, `fid.pares` debe viajar al traspaso, no solo la curva base.
    """
    base: dict[str, int] = {}
    for key, value in (tallas or {}).items():
        try:
            qty = int(value or 0)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            raw_key = str(key).strip()
            talla_key = raw_key if raw_key.lower().startswith("t") else f"t{raw_key}"
            base[talla_key] = base.get(talla_key, 0) + qty

    if not base:
        return {}

    try:
        target = int(pares_objetivo or 0)
    except (TypeError, ValueError):
        target = 0

    if target <= 0:
        return dict(sorted(base.items(), key=lambda item: talla_sort_key(item[0])))

    base_sum = sum(base.values())
    if base_sum <= 0:
        return {}
    if base_sum == target:
        return dict(sorted(base.items(), key=lambda item: talla_sort_key(item[0])))
    if target % base_sum == 0:
        factor = target // base_sum
        return {
            key: qty * factor
            for key, qty in sorted(base.items(), key=lambda item: talla_sort_key(item[0]))
        }

    scaled: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    for key, qty in sorted(base.items(), key=lambda item: talla_sort_key(item[0])):
        numerator = target * qty
        scaled[key] = numerator // base_sum
        remainders.append((numerator % base_sum, key))

    missing = target - sum(scaled.values())
    for _, key in sorted(remainders, key=lambda item: (-item[0], talla_sort_key(item[1])))[:missing]:
        scaled[key] += 1

    return {key: qty for key, qty in scaled.items() if qty > 0}
