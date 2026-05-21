# Auditoría Auto — OT-RIMEC-WEB-AUTH-514-001

## PASS si

- [ ] Login usa `usuario_v2` en **servidor** (route API), no solo cliente
- [ ] VENDEDOR y ADMIN entran; SU (IVO) y otros bloqueados
- [ ] `middleware.ts` protege rutas sin cookie
- [ ] APIs `/api/estadisticas` y `/api/consulta-pilar` devuelven 401 sin sesión
- [ ] Sin usuarios hardcodeados en TS
- [ ] `npm run build` OK; push `rimec-web` main
- [ ] Vercel prod: `/login` funciona; catálogo requiere sesión

## FAIL si

- Bypass comentado, auth solo client-side, o `NEXT_PUBLIC_SERVICE_ROLE`

## Prueba manual (director solo observa)

| Usuario | Categoría | Resultado esperado |
|---------|-----------|-------------------|
| CESAR | VENDEDOR | OK |
| HECTOR | ADMIN | OK |
| IVO | SU | Bloqueado |
