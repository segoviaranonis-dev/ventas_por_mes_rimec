# Nexus Holding — Memoria estrategica

> Documento canónico para entender **por qué existe** Nexus y qué se está construyendo.  
> No reemplaza las OT ni los docs técnicos; les da dirección.

---

## 1. Director del proyecto

**Hector** lidera el proyecto desde una combinación poco común: calle comercial, formación contable y aprendizaje autodidacta en programación.

- Formación: Ciencias Contables, Universidad Nacional de Asunción.
- Experiencia: operación real, venta, proveedores, importadora, clientes y flujo administrativo.
- Perfil de trabajo: aprende haciendo, valida contra negocio real y exige funcionamiento operativo, no demos decorativas.
- Necesidad de soporte IA: arquitectura, orden documental, supervisión técnica y ejecución asistida.

La IA no reemplaza la dirección del negocio. La IA ayuda a convertir criterio comercial en sistemas confiables.

---

## 2. Objetivo empresarial

El objetivo no es solo hacer reportes ni paginas web.

**Objetivo:** brindar soluciones a una importadora para mejorar rentabilidad, trazabilidad y control operativo, con ambición de absorber progresivamente sus procesos y proveerle un sistema operativo completo.

La estrategia es entrar por valor inmediato y avanzar hacia operación:

1. Mostrar informacion gerencial clara.
2. Ganar confianza con Sales Report.
3. Conectar stock, ventas, transito y web.
4. Reemplazar herramientas aisladas por procesos propios.
5. Convertir Nexus en sistema operativo de la importadora y del holding.

---

## 3. Estrategia de absorcion

### Fase de entrada: Report

**Sales Report** es la puerta de entrada. Permite demostrar valor a direccion con datos que ya existen:

- ventas por periodo;
- marcas;
- clientes;
- vendedores;
- tipo y categoria;
- monto y cantidad.

Regla: Sales Report usa `registro_ventas_general_v2` y maestras `_v2`. No usa pilares operativos.

### Fase de control: Retail

**Retail** muestra stock multi-tienda, reposicion y lectura por producto. A diferencia de Sales Report, Retail sí puede usar pilares porque su rol es operativo.

### Fase comercial visible: Ventas con Fotos

**Ventas con Fotos** absorbe el trabajo viejo `info_ventas_fotos` dentro de `report`.

Debe servir para mostrar a clientes/direccion:

- ventas por cliente;
- periodo;
- marca;
- tipo CALZADOS;
- monto;
- cantidad;
- imagen real del calzado desde Storage.

Este modulo no debe depender de PyQt, MySQL Railway ni carpetas UNC.

### Fase operativa mayorista: RIMEC Web

**RIMEC Web** gestiona preventa / venta en transito:

- catalogo mayorista;
- carrito vendedor;
- pedido web;
- FI;
- PDF;
- control por PP, llegada y origen.

### Fase Bazar: Bazar Web

**Bazar Web** conecta la importadora con venta final:

- stock web;
- pedido cliente;
- reserva;
- precio web;
- proceso administrativo posterior.

---

## 4. Entrega prioritaria del lunes

Entregar funcionando al 100%:

| Producto | Ruta / repo | Estado esperado |
|---|---|---|
| Sales Report | `report` | Reporte gerencial confiable |
| Retail | `report` | Stock / reposicion visible |
| Ventas con Fotos | `report` | Informe con fotos reales del calzado |
| Bazar Web | `bazzar-web` | Venta final y flujo administrativo casi cerrado |

RIMEC Web y Nexus Streamlit sostienen la operacion detras de esas entregas.

---

## 5. Metodologia de trabajo con IA

### GPT — asistente personal senior

Rol principal:

- vision macro del holding;
- arquitectura;
- priorizacion;
- auditoria;
- deteccion de riesgos;
- redaccion de ordenes de trabajo;
- revision de lo ejecutado por Claude Code.

GPT modifica codigo solo cuando:

- el cambio es muy delicado;
- la correccion requiere criterio arquitectonico;
- la ejecucion por otro agente pondria en riesgo el sistema.

### Claude Code — ejecutor

Rol principal:

- ejecutar ordenes concretas;
- modificar codigo;
- correr pruebas;
- reportar diffs y resultados.

Claude Code no debe reinterpretar la estrategia ni tocar otros modulos sin orden explícita.

---

## 6. Principios no negociables

1. **El negocio manda.** El sistema implementa reglas de direccion.
2. **Excel proveedor es ley** cuando es fuente de la operacion.
3. **Una sola verdad por dato.** No duplicar reglas en varios lugares sin indicar fuente canónica.
4. **Sales Report no usa pilares.** Retail, Motor, RIMEC Web y Bazar sí pueden usarlos según su rol.
5. **Foto del producto vende confianza.** En informes con fotos, si la foto falta debe verse claramente.
6. **No romper lo que opera.** Refactorizar solo despues de estabilizar.
7. **Todo cambio debe poder explicarse.** Si no se puede explicar, no se debe ejecutar.
8. **Las OT documentan ejecucion; la memoria documenta direccion.**

---

## 7. Frase guia

Nexus no es un conjunto de pantallas. Es la construccion gradual de un sistema operativo comercial, administrativo y gerencial para tomar control de la operacion.
