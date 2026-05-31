# OT-<REPO>-<MODULO>-<NUMERO> — <Titulo>

> Estado: BORRADOR  
> Repo: `<repo>`  
> Rama base: `main`  
> Responsable ejecución: Claude Code  
> Responsable revisión: GPT  
> Director: Hector

---

## 1. Objetivo

Describir en una frase qué debe quedar funcionando.

---

## 2. Contexto

Explicar por qué existe esta OT y qué problema resuelve.

---

## 3. Alcance permitido

Archivos, carpetas o módulos que Claude Code puede tocar:

```txt
repo/ruta
```

---

## 4. No tocar

Archivos, carpetas o módulos prohibidos:

```txt
repo/ruta
```

---

## 5. Reglas de negocio

- Regla 1.
- Regla 2.
- Regla 3.

---

## 6. Pasos de ejecución

1. Revisar `git status`.
2. Leer archivos relevantes.
3. Implementar cambio.
4. Correr pruebas.
5. Guardar evidencia.
6. Commit y push.

---

## 7. Pruebas obligatorias

| Prueba | Comando / acción | Resultado esperado |
|---|---|---|
| Build | `npm run build` | Pasa |
| Lint | `npm run lint` | Pasa o warnings conocidos |
| Manual | Navegar flujo | Funciona |

---

## 8. Evidencia requerida

- Screenshot o video.
- Salida de comandos.
- Query SQL si aplica.
- Hash de commit.

---

## 9. Criterio de cierre

La OT se cierra si:

- cumple objetivo;
- no rompe módulos prohibidos;
- pruebas obligatorias pasan;
- GPT verifica;
- Director acepta.

---

## 10. Reporte esperado de Claude Code

```txt
Resumen:
Archivos tocados:
Pruebas:
Evidencia:
Riesgos:
Commit/PR:
```
