# Nexus Holding — Reglas canónicas

> Fuente compacta para agentes y humanos.  
> Si una regla dispersa contradice este documento, se debe revisar el documento viejo y corregirlo o marcarlo como historico.

---

## 1. Jerarquia documental

Cuando haya conflicto, manda este orden:

1. **Orden directa del Director** en la conversacion actual.
2. `docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md` — direccion y estrategia.
3. `docs/NEXUS_HOLDING_MANUAL_PROCEDIMIENTOS.md` — forma de trabajar.
4. `docs/NEXUS_HOLDING_PROTOCOLO_CLAUDE_CODE.md` — comunicación con ejecutores.
5. `docs/RIMEC_MISION_VISION_POLITICA.md` — politica macro RIMEC/Nexus.
6. `docs/RIMEC_NOMENCLATURA_PILARES.md` y `docs/RIMEC_PILARES_CINCO.md` — datos/pilares.
7. `.cursor/rules/*.mdc` — reglas ejecutables para agentes.
8. `docs/OT_REGISTRO_ESTADO.md` y `docs/ot/INDICE_OT.md` — estado vivo de OT.
9. OT individuales, auditorias y evidencias.
10. README antiguos, contextos historicos y docs de modulo.

---

## 2. Productos y responsabilidades

| Producto | Repo | Rol | Datos principales |
|---|---|---|---|
| Nexus Streamlit | `ventas_por_mes_rimec` | Sistema operativo interno | Supabase operativa, pilares, IC, PP, FI |
| Report | `report` | Cara gerencial / direccion | `registro_ventas_general_v2`, maestras `_v2`, retail staging |
| RIMEC Web | `rimec-web` | Venta mayorista / transito | `v_stock_rimec`, PP, carrito vendedor |
| Bazar Web | `bazzar-web` | Venta final / e-commerce | `v_stock_web`, pedidos web, reservas |
| Info Ventas Fotos | `info_ventas_fotos` | Legacy a absorber | Debe migrar a `report/ventas-fotos` |

---

## 3. Reglas de datos

### Sales Report

- Usa `registro_ventas_general_v2`.
- Usa maestras: `cliente_v2`, `marca_v2`, `tipo_v2`, `categoria_v2`, `vendedor_v2`, `cadena_v2`.
- No usa pilares operativos (`linea`, `referencia`, `material`, `color`, `talla`).
- El tipo/categoria son el puente conceptual con la operacion.

### Retail

- Puede usar pilares.
- Depende de Excel multi-tienda / staging.
- No reemplaza al Motor de precios.

### Motor de precios

- Fuente: Excel proveedor + biblioteca de casos.
- El caso comercial vive en `precio_evento` / `precio_evento_caso` / `precio_lista`.
- No usar `linea.caso_id` como fuente nueva.

### RIMEC Web

- Catalogo desde `v_stock_rimec`.
- Estilo y Tipo 1 desde `linea_referencia`, no desde `linea.caso_id`.
- Tarjetas multi-origen: mismo SKU con distinto origen se muestra separado.

### Bazar Web

- Catalogo desde `v_stock_web`.
- Reservas solo por RPC transaccional definida para stock.
- No calcular precio final con datos enviados por cliente.

---

## 4. Pilares

Pilares canónicos:

1. `linea`
2. `referencia`
3. `material`
4. `color`
5. `talla` / grada

Reglas:

- FK siempre `{pilar}_id`.
- Codigo proveedor siempre `codigo_proveedor` en maestros.
- Copias denormalizadas: `{pilar}_codigo_proveedor`.
- No inventar alias nuevos como `codigo_linea`, `linea_cod`, `ref_cod` en codigo nuevo.
- Excel STYLE `1184.100` se parsea como enteros, no como float.

---

## 5. Report / Ventas con Fotos

El modulo `ventas-fotos` en `report` debe absorber el flujo legacy `info_ventas_fotos`.

Reglas:

- Fuente de ventas: `registro_ventas_general_v2`.
- Tipo: solo CALZADOS desde `tipo_v2`.
- Categoria: usar `categoria_v2`.
- Marcas: no listar `marca_v2` plano; usar relacion por tipo (`marca_tipo_v2`) cuando exista.
- Foto: obligatoria desde Supabase Storage bucket `productos`.
- El campo `imagen` debe resolver a una URL publica tipo:
  `https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/1122-828-5881-71523.jpg`
- Si falta foto, mostrar error visual claro; no esconder el problema.
- Transito puede quedar para fase posterior si no esta definido.

---

## 6. Reglas de operacion

- Imports masivos: latido cada 60 segundos.
- UI Streamlit: tras escritura exitosa usar `core.ux_celebrate`.
- No matar datos productivos con reset sin autorizacion explícita.
- No commitear secretos.
- No introducir dependencias pesadas sin necesidad.
- Probar con runtime real antes de afirmar que algo funciona.

---

## 7. Metodologia GPT / Claude Code

GPT:

- planea;
- supervisa;
- audita;
- redacta OT;
- revisa impacto macro.

Claude Code:

- ejecuta;
- modifica codigo;
- corre pruebas;
- entrega evidencia.

Regla de trabajo:

> Si la tarea es de arquitectura, reglas, priorizacion o supervision, la hace GPT.  
> Si la tarea es ejecucion de codigo acotado, la hace Claude Code siguiendo instrucciones.

---

## 8. Documentos historicos

Los docs viejos no se borran por defecto. Se clasifican:

- **Canonico:** fuente actual.
- **Operativo:** runbook o OT vigente.
- **Historico:** contexto de una fecha o fase cerrada.
- **Legacy:** contiene reglas superadas; conservar solo si aporta trazabilidad.

Cada documento nuevo debe indicar su rol.
