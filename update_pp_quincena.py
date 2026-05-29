#!/usr/bin/env python3
"""
Script temporal para agregar función de actualización de quincena en PP.
Esta función se agregará a modules/pedido_proveedor/logic.py
"""

code_snippet = '''
def update_quincena_pp(pp_id: int, quincena_id: int | None) -> bool:
    """
    Actualiza quincena_arribo_id de un PP existente.
    Usado para asignar manualmente quincenas a PPs antiguos (migración de datos).
    """
    from core.database import commit_query
    return commit_query(
        "UPDATE pedido_proveedor SET quincena_arribo_id = :qid WHERE id = :pp_id",
        {"qid": quincena_id, "pp_id": pp_id}
    )
'''

print("Agregar esta función a modules/pedido_proveedor/logic.py:")
print(code_snippet)
