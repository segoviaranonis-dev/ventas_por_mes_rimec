# Agent memory - Nexus Core / ventas_por_mes_rimec

## Rol del repo

`ventas_por_mes_rimec` es Nexus Core: el sistema operativo interno de RIMEC.
Incluye Streamlit, motor de precios, pedido proveedor, aprobaciones, compra legal, stock, docs y politicas del ecosistema.

## Hector y forma de trabajo

Hector es el Director del negocio. Aprende haciendo, necesita pasos concretos y evidencia.
No asumir que conoce Git, Next, Vercel, JSON o Streamlit.
Explicar corto, ejecutar con cuidado y dejar pruebas.

## Leyes centrales

- GitHub es la verdad central; la PC de Hector es taller; Vercel/Streamlit son vidriera.
- Apps cerradas: Nexus Core, Report, RIMEC Web.
- App abierta: Bazzar Web.
- Las apps cerradas deben tener login, roles, APIs protegidas, logout visible y auditoria.
- No borrar datos, carpetas ni cambios locales sin backup y autorizacion explicita.
- No tocar Bazzar Web salvo urgencia de seguridad o produccion.
- Toda decision debe apuntar a futuro sistema operativo: FK, trazabilidad, transacciones atomicas y cero confianza en frontend.

## Documentos que leer primero

- `docs/NEXUS_CORE_PROTOCOLO_TRABAJO_HECTOR.md`
- `docs/NEXUS_MAPA_VERDAD_OPERATIVA.md`
- `docs/RIMEC_MISION_VISION_POLITICA.md`
- `docs/RIMEC_PILARES_CINCO.md`
- `docs/RIMEC_NOMENCLATURA_PILARES.md`
- `docs/RIMEC_POLITICAS_BLINDADAS.md`
- `docs/NEXUS_PROTOCOLO_IMAGENES_PRODUCTO.md`
- `docs/NEXUS_HOLDING_PROTOCOLO_CLAUDE_CODE.md`

## Prioridad actual

Cerrar robustez del flujo:

```text
Pedido Proveedor + Proforma Excel + Listado de Precios
-> stock en transito con FK de pilares
-> venta/facturacion
-> CSV/exports correctos
```

Antes del CSV, cuadrar cantidades:
- comprado
- disponible en transito
- facturado / preventa
- saldo
- ingreso a deposito

## Reglas tecnicas

- Los 5 pilares son linea, referencia, material, color y grada/talla.
- Precio vive hasta linea + referencia + material.
- Color y grada identifican stock y venta.
- Usar FK (`linea_id`, `referencia_id`, etc.), no texto suelto.
- Caso comercial vive en evento/listado, no en `linea.caso_id`.
- Importaciones largas deben tener latido cada 60s.
- Tras escrituras exitosas en UI Streamlit, usar celebraciones UX existentes.

## Validacion minima

- `git status`
- prueba funcional del flujo tocado
- no vender tests inconclusos como prueba final
- si se toca UI, evidencia visual
- commit y push cuando se complete
