# Nexus Core — Índice documental canónico

> Entrada recomendada para humanos y agentes.  
> Este repo (`ventas_por_mes_rimec`, ex `control_central`) es la casa operativa de Nexus dentro de `C:\Users\hecto\Nexus_Core\`.

---

## 1. Leer primero

| Orden | Documento | Rol |
|---|---|---|
| 1 | [NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md](NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md) | Por qué existe Nexus y hacia dónde va |
| 2 | [NEXUS_HOLDING_REGLAS_CANONICAS.md](NEXUS_HOLDING_REGLAS_CANONICAS.md) | Reglas unificadas para agentes y ejecución |
| 3 | [NEXUS_HOLDING_MAPA_DOCUMENTAL.md](NEXUS_HOLDING_MAPA_DOCUMENTAL.md) | Qué documento leer y cuál es histórico |
| 4 | [RIMEC_MISION_VISION_POLITICA.md](RIMEC_MISION_VISION_POLITICA.md) | Política macro RIMEC/Nexus |
| 5 | [OT_REGISTRO_ESTADO.md](OT_REGISTRO_ESTADO.md) | Estado vivo de OT |

---

## 2. Datos y dominio

| Documento | Uso |
|---|---|
| [RIMEC_NOMENCLATURA_PILARES.md](RIMEC_NOMENCLATURA_PILARES.md) | Léxico P0 de pilares |
| [RIMEC_PILARES_CINCO.md](RIMEC_PILARES_CINCO.md) | Modelo de 5 pilares y grada |
| [RETAIL_VS_SALES.md](RETAIL_VS_SALES.md) | Diferencia Sales Report vs Retail |
| [RIMEC_POLITICAS_BLINDADAS.md](RIMEC_POLITICAS_BLINDADAS.md) | Leyes de negocio |
| [TRAZABILIDAD_PP_LISTADO.md](TRAZABILIDAD_PP_LISTADO.md) | PP, listado y evento |
| [DICCIONARIO_PRECIO_WEB.md](DICCIONARIO_PRECIO_WEB.md) | Precio web / Bazar |

---

## 3. Operación

| Documento | Uso |
|---|---|
| [../COMO_EJECUTAR.md](../COMO_EJECUTAR.md) | Puertos y comandos |
| [CONTROL_INTEGRIDAD_HOLDING.md](CONTROL_INTEGRIDAD_HOLDING.md) | Gate P1-P8 |
| [DEPLOY_MAPA_URLS.md](DEPLOY_MAPA_URLS.md) | Mapa deploy |
| [DEPLOY_STREAMLIT_512.md](DEPLOY_STREAMLIT_512.md) | Deploy Streamlit |
| [DEPLOY_VERCEL_512.md](DEPLOY_VERCEL_512.md) | Deploy Vercel |

---

## 4. Reglas ejecutables para agentes

| Archivo | Tema |
|---|---|
| `../.cursor/rules/rimec-arquitectura-unica-verdad.mdc` | Productos, procesos y única verdad |
| `../.cursor/rules/rimec-nomenclatura-pilares-p0.mdc` | Nomenclatura P0 |
| `../.cursor/rules/rimec-listado-pp-fi.mdc` | Listado, PP, FI |
| `../.cursor/rules/rimec-ley-fi-card.mdc` | Ley FI |
| `../.cursor/rules/ux-celebration.mdc` | UX post-guardado |
| `../.cursor/rules/import-heartbeat.mdc` | Latido imports |

---

## 5. Regla de conflicto

Si dos documentos se contradicen:

1. manda la instrucción directa del Director;
2. luego `NEXUS_HOLDING_REGLAS_CANONICAS.md`;
3. luego `RIMEC_MISION_VISION_POLITICA.md`;
4. luego documentos de datos/pilares;
5. luego OT y contextos históricos.

No borrar documentos históricos sin autorización. Marcar drift en el mapa documental.
