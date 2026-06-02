# Nexus Core — Protocolo simple de trabajo para Hector

Este documento existe para evitar el quilombo PC / Git / Vercel / Streamlit.

## Regla principal

**GitHub es la verdad central.**

- **Tu PC** es el taller donde probas y modificas.
- **GitHub** es el archivo maestro con historial.
- **Vercel / Streamlit** publican desde GitHub.

Flujo normal:

```text
PC o agente -> GitHub -> Vercel / Streamlit
```

Antes de probar local:

```bat
git pull
npm run dev
```

Antes de publicar:

```bat
git status
npm run build
git add .
git commit -m "mensaje claro"
git push
```

## Carpetas esperadas en `C:\Users\hecto\Nexus_Core`

| Carpeta | Producto | Uso |
|---|---|---|
| `ventas_por_mes_rimec` | Nexus operativo | Streamlit, motor, PP, compras, docs del ecosistema |
| `report` | Report / informes | Vercel, Sales Report, Retail, Ventas con fotos |
| `rimec-web` | Web RIMEC | Catalogo mayorista |
| `bazzar-web` | Bazar Web | Tienda final |
| `info_ventas_fotos` | Legacy / referencia | App vieja absorbida por Report |

## Comandos de arranque local

```bat
cd C:\Users\hecto\Nexus_Core\ventas_por_mes_rimec
streamlit run main.py
```

```bat
cd C:\Users\hecto\Nexus_Core\report
git pull
npm run dev
```

```bat
cd C:\Users\hecto\Nexus_Core\rimec-web
git pull
npm run dev
```

```bat
cd C:\Users\hecto\Nexus_Core\bazzar-web
git pull
npm run dev
```

## Que hacer cuando tu PC y Git no coinciden

Primero mirar:

```bat
git status
```

Si dice `working tree clean`, podes traer Git:

```bat
git pull
```

Si muestra archivos modificados, **no borrar**. Primero guardar evidencia:

```bat
git status
git diff --stat
```

Despues decidir:

1. Si son cambios tuyos que queres conservar: pedir ayuda antes de hacer pull.
2. Si son basura local: hacer backup o pedir que un agente lo limpie.
3. Si no sabes: no tocar, mandar captura/log.

## Script recomendado

Desde Windows:

```bat
C:\Users\hecto\Nexus_Core\ventas_por_mes_rimec\scripts\windows\sincronizar_nexus_core_desde_git.bat
```

Ese script revisa los repos uno por uno. Si hay cambios locales, se detiene para no pisar trabajo.

## Reglas para agentes

1. No borrar carpetas locales de Hector sin backup y confirmacion explicita.
2. No asumir que la PC esta igual que Git.
3. Antes de diagnosticar un bug local, pedir o revisar:
   - `git status`
   - rama actual
   - ultimo commit
   - comando usado para arrancar
4. Si Vercel funciona y PC no, primero sincronizar PC con Git.
5. Si PC funciona y Vercel no, revisar deploy y variables de entorno.

## Frase corta

**PC es taller. GitHub es verdad central. Vercel y Streamlit son vidriera.**
