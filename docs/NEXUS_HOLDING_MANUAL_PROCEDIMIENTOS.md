# Nexus Holding — Manual de procedimientos

> Rol: manual operativo único del holding.  
> Vigencia: uso diario con GPT, Claude Code y repos de `Nexus_Core`.  
> Relacionados: `NEXUS_CORE_INDEX.md`, `NEXUS_HOLDING_REGLAS_CANONICAS.md`, `docs/ot/README.md`.

---

## 1. Principio rector

Nexus se desarrolla como sistema operativo del holding. Cada cambio debe cumplir al menos una de estas funciones:

1. mejorar rentabilidad;
2. aumentar control operativo;
3. reducir dependencia de planillas o sistemas externos;
4. mejorar trazabilidad;
5. preparar absorción de procesos de la importadora.

Si una tarea no cumple ninguna, no es prioridad.

---

## 2. Estructura de trabajo

| Capa | Ubicación | Uso |
|---|---|---|
| Memoria canónica | `ventas_por_mes_rimec/docs/NEXUS_HOLDING_*.md` | Estrategia, reglas, mapa |
| OT oficiales | `ventas_por_mes_rimec/docs/ot/` | Ordenes de trabajo versionadas |
| OT operativas locales | `C:\Users\hecto\Nexus_Core\ot\` | Copia rápida para ejecución diaria |
| Código | Repo correspondiente | Implementación real |
| Evidencia | `docs/ot/evidencia/` o PR | Screenshots, logs, videos |

La copia local puede ser práctica; la versión confiable queda en Git.

---

## 3. Roles

### Director

- Define prioridad.
- Valida negocio.
- Decide si una solución es aceptable.
- Puede cambiar el orden de trabajo en cualquier momento.

### GPT

- Piensa macro.
- Ordena reglas.
- Redacta OT.
- Audita lo hecho.
- Detecta riesgos antes de que Claude Code modifique.
- Solo toca código cuando el cambio sea crítico o convenga por precisión.

### Claude Code

- Ejecuta OT.
- Modifica código.
- Corre pruebas.
- Entrega evidencia.
- No redefine arquitectura sin autorización.

---

## 4. Flujo estándar de una tarea

1. **Director expresa necesidad.**
2. **GPT convierte necesidad en OT.**
3. **Claude Code ejecuta la OT.**
4. **Claude Code reporta:**
   - archivos tocados;
   - comandos corridos;
   - evidencia;
   - errores o dudas.
5. **GPT verifica.**
6. Si pasa:
   - se commitea;
   - se actualiza PR;
   - se mueve OT a cerrada.
7. Si falla:
   - GPT redacta corrección;
   - Claude Code itera.

---

## 5. Clasificación de tareas

| Tipo | Quién lidera | Ejemplos |
|---|---|---|
| Estrategia | GPT | Definir módulos del lunes |
| Arquitectura | GPT | Separar Report vs Nexus vs Webs |
| Ejecución código | Claude Code | Crear endpoint, corregir UI |
| Debug crítico | GPT + Claude Code | Error de BD, auth, pérdida de datos |
| Documentación canónica | GPT | Manuales, reglas, protocolos |
| Refactor grande | GPT diseña, Claude ejecuta | Separar módulos gigantes |

---

## 6. Procedimiento para cambiar código

Antes de tocar código:

1. identificar repo;
2. identificar rama;
3. revisar estado git;
4. entender regla canónica afectada;
5. definir prueba mínima;
6. ejecutar cambio acotado;
7. correr prueba;
8. commitear con mensaje claro;
9. push;
10. actualizar PR.

Nunca mezclar en el mismo commit:

- seguridad + UI;
- migración + refactor;
- bugfix + cambio de diseño;
- docs + cambio funcional crítico.

---

## 7. Procedimiento para OT

Toda OT nueva debe tener:

- ID único;
- objetivo;
- contexto;
- alcance;
- reglas no negociables;
- archivos permitidos;
- archivos prohibidos;
- pasos de ejecución;
- pruebas obligatorias;
- criterio de cierre.

Plantilla: `docs/ot/PLANTILLA_OT.md`.

---

## 8. Procedimiento para reportes del lunes

Prioridad de entrega:

1. `report` — Sales Report.
2. `report` — Retail.
3. `report` — Ventas con Fotos.
4. `bazzar-web` — detalles finales.

Reglas:

- No romper Sales Report mientras se corrige Ventas con Fotos.
- No mezclar pilares dentro del Sales Report principal.
- Ventas con Fotos sí puede parsear `imagen` como molécula L-R-M-C para estadísticas.
- Las fotos deben verse o fallar con mensaje claro.

---

## 9. Procedimiento para base de datos

Antes de aplicar SQL:

1. escribir SQL en archivo versionado;
2. verificar si es idempotente (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`);
3. anotar rollback si aplica;
4. aplicar en Supabase;
5. guardar evidencia;
6. actualizar OT.

No aplicar SQL manual sin dejar archivo.

---

## 10. Procedimiento para evidencia

Evidencia válida:

- salida de `npm run build`;
- salida de `pytest`;
- screenshot;
- video corto;
- log de servidor;
- query SQL con resultado;
- link a PR.

Evidencia inválida:

- "debería funcionar";
- "compila en mi cabeza";
- screenshot que muestra error no resuelto;
- video donde el flujo falla y luego se ignora.

---

## 11. Procedimiento para documentación

Los documentos se clasifican así:

- **Canónico:** manda.
- **Operativo:** guía ejecución.
- **Histórico:** explica decisiones pasadas.
- **Legacy:** conservar solo por trazabilidad.

No crear un nuevo documento "norte" sin actualizar:

- `NEXUS_CORE_INDEX.md`;
- `NEXUS_HOLDING_MAPA_DOCUMENTAL.md`;
- `NEXUS_HOLDING_REGLAS_CANONICAS.md`.

---

## 12. Cierre de jornada

Antes de cerrar:

1. revisar qué quedó en curso;
2. revisar ramas sin push;
3. revisar PR abiertas;
4. actualizar OT;
5. dejar instrucción clara para el siguiente agente;
6. no dejar cambios críticos sin commit.

---

## 13. Regla final

La velocidad no puede destruir la trazabilidad. Si algo se hace rápido, igual debe quedar explicado, testeado y ubicable.
