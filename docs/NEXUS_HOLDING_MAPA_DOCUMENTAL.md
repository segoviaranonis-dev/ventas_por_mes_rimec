# Nexus Holding — Mapa documental

> Inventario ordenado de los documentos dispersos en `Nexus_Core`.  
> Objetivo: saber donde leer, que manda y que queda como historico.

---

## 1. Entrada recomendada

Leer en este orden:

1. `docs/NEXUS_CORE_INDEX.md`
2. `docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md`
3. `docs/NEXUS_HOLDING_REGLAS_CANONICAS.md`
4. `docs/RIMEC_MISION_VISION_POLITICA.md`
5. `docs/OT_REGISTRO_ESTADO.md`

---

## 2. Documentos canónicos

| Documento | Rol |
|---|---|
| `docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md` | Estrategia de absorcion y vision del holding |
| `docs/NEXUS_HOLDING_REGLAS_CANONICAS.md` | Reglas compactas para agentes/humanos |
| `docs/RIMEC_MISION_VISION_POLITICA.md` | Politica macro de Nexus/RIMEC |
| `docs/RIMEC_NOMENCLATURA_PILARES.md` | Lexico P0 de pilares |
| `docs/RIMEC_PILARES_CINCO.md` | Modelo de 5 pilares y grada |
| `docs/OT_REGISTRO_ESTADO.md` | Estado vivo de OT |
| `.cursor/rules/*.mdc` | Reglas ejecutables para agentes Cursor |

---

## 3. Documentos operativos

| Documento | Uso |
|---|---|
| `COMO_EJECUTAR.md` | Puertos y comandos locales |
| `docs/CONTROL_INTEGRIDAD_HOLDING.md` | Control P1-P8 / cierre de OT |
| `docs/DEPLOY_MAPA_URLS.md` | Mapa deploy |
| `docs/DEPLOY_STREAMLIT_512.md` | Deploy Streamlit |
| `docs/DEPLOY_VERCEL_512.md` | Deploy Vercel |
| `DISASTER_RECOVERY.md` | Recuperacion |
| `CONFIGURAR_BACKUPS.md` | Backups |

---

## 4. Documentos de dominio

| Tema | Documentos |
|---|---|
| Ley FI | `docs/COMPRA_WEB_LEY_FI.md`, `.cursor/rules/rimec-ley-fi-card.mdc` |
| PP / listado / FI | `docs/TRAZABILIDAD_PP_LISTADO.md`, `.cursor/rules/rimec-listado-pp-fi.mdc` |
| Precio Web | `docs/DICCIONARIO_PRECIO_WEB.md`, `OT-WEB-PRECIO-509-001.md` |
| Digitacion | `docs/ALBANIL_MODULO_DIGITACION.md`, `OT-DIGITACION-IC2-518-001.md` |
| Sales Report | `modules/sales_report/CONTEXT.md`, `modules/sales_report/GESTION_DETALLADA_MAPA_TABLA8.md` |
| Retail vs Sales | `docs/RETAIL_VS_SALES.md` |
| UX / latido | `.cursor/rules/ux-celebration.mdc`, `.cursor/rules/import-heartbeat.mdc` |

---

## 5. Repos web hermanos

### `report`

| Documento | Rol |
|---|---|
| `docs/MEMORIA_HOLDING_REPORT.md` | Memoria del producto Report |
| `docs/MODULO_REPORT_LEYES_DISENO.md` | Leyes visuales y paridad Streamlit |
| `docs/DISENO_DATOS_SQL_KPI_JERARQUIA.md` | Contrato SQL/KPI |
| `docs/DISENO_DESCRIPCION_8_TABLAS_INFORME_VENTAS.md` | 8 tablas del informe |
| `DEPLOY_VERCEL.md` | Deploy Report |

### `rimec-web`

| Documento | Rol |
|---|---|
| `.cursor/rules/rimec-web-catalogo.mdc` | Regla principal catalogo mayorista |
| `DIAGNOSTICO_VERCEL.md` | Runbook Vercel |
| `AGENTS.md` | Aviso Next.js docs locales |

### `bazzar-web`

| Documento | Rol |
|---|---|
| `CONTEXT.md` | Contexto operativo vivo de Bazar |
| `docs/NEXUS_ARQUITECTURA.md` | Arquitectura historica |
| `docs/ROADMAP_ECOMMERCE.md` | Roadmap e-commerce |
| `docs/NEXUS_MISION.md` | Mision historica Bazar/Nexus |

---

## 6. Documentos a revisar por drift

| Documento | Problema |
|---|---|
| `README.md` | Decia `app.py`; el entrypoint real es `main.py` |
| `docs/RIMEC_CONTEXTO.md` | Mezcla contexto historico con reglas actuales |
| `bazzar-web/docs/NEXUS_OBJETIVO_ACTUAL.md` | Fase antigua; puede contradecir `CONTEXT.md` |
| `bazzar-web/docs/NEXUS_ARQUITECTURA.md` | Menciona vistas legacy como `v_catalogo_web` |
| `rimec-web/README.md` | Plantilla generica Next.js, poco contexto RIMEC |

---

## 7. Politica para nuevos documentos

Todo documento nuevo debe empezar con:

1. rol del documento;
2. fecha o vigencia;
3. si es canonico, operativo, historico o legacy;
4. documentos relacionados.

No crear otro "documento unico de norte" sin actualizar este mapa.
