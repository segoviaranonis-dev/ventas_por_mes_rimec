# Checklist auditoría Auto — OT-DEPLOY-GIT-VERCEL-512-001

## Git

- [ ] https://github.com/segoviaranonis-dev/ventas_por_mes_rimec — `main` con `main.py`, `requirements.txt`
- [ ] https://github.com/segoviaranonis-dev/rimec-web — sin `.env.local` en árbol
- [ ] https://github.com/segoviaranonis-dev/bazzar-web — idem
- [ ] https://github.com/segoviaranonis-dev/report — idem

## Vercel (producción)

- [ ] RIMEC Web abre (mayoristas)
- [ ] Bazzar Web abre (tienda)
- [ ] Report abre (`/rimec` o home)

## Streamlit

- [ ] Nexus carga hub sin error DB

## Seguridad

- [ ] Buscar en GitHub repo → no aparece `service_role` ni `re_` en último commit

## Veredicto

PASS si C1–C4 evidencia + URLs en `docs/DEPLOY_MAPA_URLS.md`.
