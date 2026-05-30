# RIMEC — Nexus Core

Plataforma operativa Importadora RIMEC: Streamlit + Supabase.  
Repos hermanos:

- **`report`**: Sales Report, Retail y Ventas con Fotos.
- **`rimec-web`**: venta mayorista / tránsito.
- **`bazzar-web`**: tienda Bazar / venta final.

## Documentación principal

| Documento | Uso |
|-----------|-----|
| [docs/NEXUS_CORE_INDEX.md](docs/NEXUS_CORE_INDEX.md) | **Entrada canónica documental** |
| [docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md](docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md) | Estrategia del holding |
| [docs/NEXUS_HOLDING_REGLAS_CANONICAS.md](docs/NEXUS_HOLDING_REGLAS_CANONICAS.md) | Reglas unificadas |
| [docs/OT_REGISTRO_ESTADO.md](docs/OT_REGISTRO_ESTADO.md) | **Estado de todas las OT** |
| [docs/RIMEC_MISION_VISION_POLITICA.md](docs/RIMEC_MISION_VISION_POLITICA.md) | Norte estratégico |
| [docs/RIMEC_PILARES_CINCO.md](docs/RIMEC_PILARES_CINCO.md) | 5 pilares + grada |
| [COMO_EJECUTAR.md](COMO_EJECUTAR.md) | Arranque local Nexus |

## Estado operativo (mayo 2026)

Hilo **PP-2026-0001 / CL-2026-0001** cerrado: traspaso 44 pares, depósito web, Ley FI, **precio Bazar con markup por caso** (OT-509).

Próximo recomendado: **OT-FI-CASO-508 Fase 2** (persistir caso al crear FI).

## Ejecución local

```powershell
cd ventas_por_mes_rimec-main
streamlit run main.py
```

Credenciales: `.streamlit/secrets.toml`
