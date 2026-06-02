# Cola de trabajo — MARTA y YAMBAI

> Rol: tablero operativo único para que el Director pueda decir  
> **"MARTA, ejecutá tu OT pendiente"** o **"YAMBAI, ejecutá tu OT pendiente"**.

---

## Regla de uso

Cada albañil toma **la primera OT en estado `LISTA_PARA_EJECUTAR`** de su tabla.

Al terminar, debe escribir su respuesta en:

```txt
docs/ot/respuestas/<ALBANIL>/<OT_ID>_RESPUESTA.md
```

Y dejar evidencia en:

```txt
docs/ot/evidencia/<OT_ID>/
```

---

## MARTA — Cursor Desktop / Report

| Prioridad | OT | Repo | Estado | Archivo OT | Respuesta esperada |
|---:|---|---|---|---|---|
| 1 | OT-REPORT-PDF-ESTADISTICAS-005 | `report` | EN_EJECUCION | `report/docs/ot/en_curso/OT-REPORT-PDF-ESTADISTICAS-005.md` | `docs/ot/respuestas/MARTA/OT-REPORT-PDF-ESTADISTICAS-005_RESPUESTA.md` |

### Alcance actual de MARTA

- `report`
- Sales Report / Retail / Ventas con Fotos
- PDF ejecutivo
- UI estilo Report

### Prohibido para MARTA

- `ventas_por_mes_rimec` runtime
- `rimec-web`
- `bazzar-web`
- base de datos productiva sin OT explicita

---

## YAMBAI — Claude Code / Nexus operativo

| Prioridad | OT | Repo | Estado | Archivo OT | Respuesta esperada |
|---:|---|---|---|---|---|
| 1 | OT-NEXUS-FI-EDITAR-ITEMS-ROBUSTEZ-001 | `ventas_por_mes_rimec` | LISTA_PARA_EJECUTAR | `docs/ot/en_curso/OT-NEXUS-FI-EDITAR-ITEMS-ROBUSTEZ-001.md` | `docs/ot/respuestas/YAMBAI/OT-NEXUS-FI-EDITAR-ITEMS-ROBUSTEZ-001_RESPUESTA.md` |
| 2 | OR-NEXUS-PP-2DA-MAYO-PRECHECK-001 | `ventas_por_mes_rimec` | LISTA_PARA_EJECUTAR | `docs/ot/en_curso/OR-NEXUS-PP-2DA-MAYO-PRECHECK-001.md` | `docs/ot/respuestas/YAMBAI/OR-NEXUS-PP-2DA-MAYO-PRECHECK-001_RESPUESTA.md` |

### Alcance actual de YAMBAI

- Nexus Streamlit
- Pedido Proveedor
- Compra Legal
- Facturación
- Depósito
- Compra Web / Depósito Web

### Prohibido para YAMBAI

- `report` salvo OT explícita
- `rimec-web` salvo OT explícita
- `bazzar-web` salvo OT explícita

---

## Frases operativas para el Director

### Para iniciar trabajo

```txt
MARTA, ejecutá tu OT pendiente.
YAMBAI, ejecutá tu OT pendiente.
```

### Para reportar cierre a GPT

```txt
MARTA terminó.
YAMBAI terminó.
```

GPT buscará la respuesta esperada en la tabla de arriba.

---

## Estados permitidos

| Estado | Significado |
|---|---|
| BORRADOR | Aun no lista |
| LISTA_PARA_EJECUTAR | Puede ejecutarse |
| EN_EJECUCION | Albañil trabajando |
| EN_REVISION_GPT | GPT debe auditar |
| CORRECCION_REQUERIDA | Debe volver al albañil |
| CERRADA | Director/GPT aprobaron |

---

## Regla de foco

MARTA y YAMBAI no trabajan el mismo repo al mismo tiempo salvo orden explícita.

---

## Bloqueo arquitectónico activo

| Frente | Estado | Motivo | Responsable |
|---|---|---|---|
| Flujo FK/Eventos Nexus → RIMEC Web → Bazzar Web | BLOQUEADO_PARA_ALBANILES | Riesgo legal/comercial por inconsistencias entre catálogo, estadísticas, stock, FI, compra y Bazzar Web | GPT |

Regla:

```txt
YAMBAI, MARTA y MARTA2 no deben modificar arquitectura FK/eventos sin una OT específica emitida por GPT.
```

Pueden diagnosticar si se les pide, pero no redefinir fuentes de verdad ni filtros.
