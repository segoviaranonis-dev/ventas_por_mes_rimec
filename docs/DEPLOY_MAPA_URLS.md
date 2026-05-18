# Mapa URLs — Deploy OT-512

**Última actualización:** 2026-05-18

---

## Producción

| Producto | Plataforma | URL | Estado |
|----------|------------|-----|--------|
| **Nexus** (Streamlit) | Streamlit Cloud | `https://COMPLETAR.streamlit.app` | ⏸ Pendiente deploy usuario |
| **RIMEC Web** (mayoristas) | Vercel | `https://COMPLETAR.vercel.app` | ⏸ Pendiente deploy usuario |
| **Bazzar Web** (tienda) | Vercel | `https://COMPLETAR.vercel.app` | ⏸ Pendiente deploy usuario |
| **Report** (informes) | Vercel | `https://COMPLETAR.vercel.app` | ⏸ Pendiente deploy usuario |

---

## Repositorios GitHub

| Producto | Repo | Último commit OT-512 |
|----------|------|----------------------|
| Nexus | https://github.com/segoviaranonis-dev/ventas_por_mes_rimec | `0746cf6` |
| RIMEC Web | https://github.com/segoviaranonis-dev/rimec-web | `f351e0d` |
| Bazzar Web | https://github.com/segoviaranonis-dev/bazzar-web | `cb33393` |
| Report | https://github.com/segoviaranonis-dev/report | `84da2a3` |

---

## Local (desarrollo)

| Producto | Puerto | Comando |
|----------|--------|---------|
| Nexus | 8501 | `streamlit run main.py` |
| RIMEC Web | 3001 | `npm run dev` |
| Bazzar Web | 3000 | `npm run dev` |
| Report | 3000 | `npm run dev` |

*RIMEC Web y Report no comparten puerto — son proyectos separados.*

---

## Instrucciones deploy

- **Vercel (3 webs):** ver `docs/DEPLOY_VERCEL_512.md`
- **Streamlit (Nexus):** ver `docs/DEPLOY_STREAMLIT_512.md`

---

## Post-deploy

Una vez completado el deploy:

1. Actualizar este archivo con URLs reales
2. Actualizar `OT-DEPLOY-GIT-VERCEL-512-001-EVIDENCIA.json` con URLs y checks
3. Marcar OT-512 como **CERRADA** en `docs/OT_REGISTRO_ESTADO.md`
