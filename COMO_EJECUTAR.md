# CÓMO EJECUTAR EL SISTEMA

## Sistema Principal (Importadora - Streamlit)
1. Abrir terminal en: C:\Users\hecto\Nexus_Core\ventas_por_mes_rimec
2. Ejecutar: streamlit run main.py
3. Abrir navegador en: http://localhost:8501

## Report (Sales Report + Retail + Ventas con Fotos)
1. Abrir terminal en: C:\Users\hecto\Nexus_Core\report
2. Ejecutar: npm run dev
3. Abrir navegador en: http://localhost:3000

## Bazar Web (clientes finales - Next.js)
1. Abrir terminal en: C:\Users\hecto\Nexus_Core\bazzar-web
2. Ejecutar: npm run dev
3. Abrir navegador en el puerto asignado por Next.js (normalmente http://localhost:3000 si Report no está corriendo)

## Web RIMEC (vendedores mayoristas - Next.js)
1. Abrir terminal en: C:\Users\hecto\Nexus_Core\rimec-web
2. Ejecutar: npm run dev
3. Abrir navegador en: http://localhost:3001

## RESUMEN DE PUERTOS
- localhost:8501 → Streamlit (administración RIMEC)
- localhost:3000 → Report (Sales Report / Retail / Ventas con Fotos)
- localhost:3001 → RIMEC Web (vendedores mayoristas)
- Bazar Web → 3000 si está libre; si no, Next.js asigna otro puerto

## Para ejecutar todo al mismo tiempo
Abrir terminales separadas y ejecutar un servicio por terminal.
