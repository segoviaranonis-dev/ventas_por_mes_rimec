# 📸 WORKFLOW COMPLETO - FOTOS RETAIL

**Flujo completo desde red hasta Storage optimizado**

---

## 🎯 OBJETIVO

Copiar fotos faltantes desde servidor de red y generar miniaturas optimizadas para Tablet Bazzar.

---

## 📋 PASOS

### **PASO 1: Copiar fotos faltantes desde red**

**Script:** `buscador_de_fotos_retail.py`

**Comando:**
```powershell
cd C:\Users\hector\Nexus_Core\control_central
python tools\buscador_de_fotos_retail.py --auto
```

**¿Qué hace?**
1. Lee `registro_st_vt_rc_reposicion` → columna `imagen_nombre`
2. Lista Storage Supabase bucket `productos`
3. Calcula faltantes
4. Busca en: `\\10.18.3.1\home\img_art`
5. Copia a: `C:\Users\hecto\Documents\Prg_locales\proyectos\imagenes`
6. **NO sube** a Storage (solo copia local)

**Rutas configuradas:**
- Origen (red): `\\10.18.3.1\home\img_art`
- Respaldo: `C:\Users\hecto\Documents\Prg_locales\proyectos\imagenes`

**Salida:**
```
diagnostico_fotos_retail/YYYYMMDD_HHMMSS/
├── imagenes_db.csv
├── faltantes_storage.csv
├── encontrados_local.csv
└── faltantes_local.csv
```

---

### **PASO 2: Convertir a miniaturas**

**Script:** `convertir_miniaturas_retail.py`

**Comando:**
```powershell
python tools\convertir_miniaturas_retail.py
```

**¿Qué hace?**
1. Lee de: `C:\Users\hecto\Documents\Prg_locales\proyectos\imagenes`
2. Genera 3 tamaños:
   - `thumb_200/` → 200x200px (grid)
   - `thumb_400/` → 400x400px (tarjetas)
   - `thumb_800/` → 800x800px (modal)
3. Guarda en: `C:\Users\hecto\Documents\Prg_locales\proyectos\miniaturas`
4. Optimiza: JPEG calidad 85%, progressive, crop centrado

**Salida:**
```
C:\Users\hecto\Documents\Prg_locales\proyectos\miniaturas/
├── thumb_200/
│   ├── 1184-1101-SINT-NEGRO.jpg (20 KB)
│   ├── 1184-1161-SINT-NEGRO.jpg (22 KB)
│   └── ...
├── thumb_400/
│   ├── 1184-1101-SINT-NEGRO.jpg (45 KB)
│   └── ...
└── thumb_800/
    ├── 1184-1101-SINT-NEGRO.jpg (95 KB)
    └── ...
```

**Reporte:**
```
reportes_miniaturas/YYYYMMDD_HHMMSS/
└── conversion_miniaturas.csv
```

---

### **PASO 3: Subir miniaturas a Storage (opcional)**

**Opciones:**

#### A) Con el buscador (interactivo)
```powershell
python tools\buscador_de_fotos_retail.py
```
- Selecciona carpeta ORIGEN: `miniaturas/thumb_200`
- Selecciona carpeta RESPALDO
- Confirma upload

#### B) Manualmente via Supabase Dashboard
```
https://supabase.com
→ Storage
→ productos
→ Upload files
```

---

## 📊 ESTADÍSTICAS TÍPICAS

### Fotos originales (red)
```
Formato: JPG, PNG
Tamaño: 500 KB - 3 MB
Dimensiones: 1000x1000 a 3000x3000
```

### Miniaturas generadas
```
thumb_200: ~20 KB  (reducción 95%)
thumb_400: ~45 KB  (reducción 92%)
thumb_800: ~95 KB  (reducción 85%)
```

### Velocidad de conversión
```
Promedio: 150ms por imagen
100 fotos: ~15 segundos
500 fotos: ~75 segundos
```

---

## 🔧 COMANDOS COMPLETOS

### Flujo automático completo
```powershell
# 1. Copiar faltantes desde red
python tools\buscador_de_fotos_retail.py --auto

# 2. Convertir a miniaturas
python tools\convertir_miniaturas_retail.py

# 3. Verificar resultado
ls "C:\Users\hecto\Documents\Prg_locales\proyectos\miniaturas\thumb_200"
```

### Solo diagnóstico (sin copiar)
```powershell
python tools\buscador_de_fotos_retail.py --auto --dry-run
```

### Rutas personalizadas
```powershell
python tools\buscador_de_fotos_retail.py \
  --origen "D:\Fotos_Red" \
  --respaldo "D:\Respaldo"

python tools\convertir_miniaturas_retail.py \
  --origen "D:\Respaldo" \
  --destino "D:\Miniaturas"
```

### Solo generar thumb_200
```powershell
python tools\convertir_miniaturas_retail.py --tamanios 200
```

### Mayor calidad (archivos más grandes)
```powershell
python tools\convertir_miniaturas_retail.py --calidad 95
```

---

## 🗂️ ESTRUCTURA DE ARCHIVOS

```
\\10.18.3.1\home\img_art\                    # Origen red
├── 1184-1101-SINT-NEGRO.jpg (2.1 MB)
├── 1184-1161-SINT-NEGRO.jpg (1.8 MB)
└── ...

↓ PASO 1: buscador_de_fotos_retail.py

C:\Users\hecto\Documents\Prg_locales\proyectos\imagenes\  # Respaldo local
├── 1184-1101-SINT-NEGRO.jpg (2.1 MB)
├── 1184-1161-SINT-NEGRO.jpg (1.8 MB)
└── ...

↓ PASO 2: convertir_miniaturas_retail.py

C:\Users\hecto\Documents\Prg_locales\proyectos\miniaturas\  # Miniaturas
├── thumb_200/
│   ├── 1184-1101-SINT-NEGRO.jpg (18 KB)
│   └── ...
├── thumb_400/
│   ├── 1184-1101-SINT-NEGRO.jpg (42 KB)
│   └── ...
└── thumb_800/
    ├── 1184-1101-SINT-NEGRO.jpg (89 KB)
    └── ...

↓ PASO 3: Upload manual o automático

Supabase Storage/productos/                  # Storage cloud
├── 1184-1101-SINT-NEGRO.jpg (thumb_200)
├── 1184-1161-SINT-NEGRO.jpg (thumb_200)
└── ...
```

---

## ⚠️ TROUBLESHOOTING

### Error: "Carpeta origen no existe o no es accesible"
```
Causa: Red \\10.18.3.1 no disponible
Fix:   Verificar conexión VPN o red local
       ping 10.18.3.1
```

### Error: "Falta instalar Pillow"
```
Causa: PIL/Pillow no instalado
Fix:   python -m pip install Pillow
```

### Fotos muy grandes (>100 KB thumb_200)
```
Causa: Calidad muy alta o imágenes complejas
Fix:   python tools\convertir_miniaturas_retail.py --calidad 75
```

### Solo se convirtieron algunas fotos
```
Causa: Formatos no soportados o corruptas
Fix:   Ver reportes_miniaturas/*/conversion_miniaturas.csv
       Columna "error" muestra detalles
```

---

## 📝 REQUISITOS

### Python
```
Python 3.11+
```

### Librerías
```bash
pip install requests    # Para buscador
pip install Pillow      # Para miniaturas
```

### Acceso
```
- Red: \\10.18.3.1\home\img_art (lectura)
- Local: C:\Users\hecto\Documents\Prg_locales\proyectos (escritura)
- Supabase: SUPABASE_URL + SERVICE_ROLE_KEY (en .env.local)
```

---

## 🎯 CASOS DE USO

### Caso 1: Primera población
```
Situación: Storage vacío, BD tiene 500 imágenes

1. python tools\buscador_de_fotos_retail.py --auto
   → Copia 500 fotos de red a local

2. python tools\convertir_miniaturas_retail.py
   → Genera 1500 miniaturas (3 tamaños × 500)

3. Subir thumb_200/ a Storage manualmente
```

### Caso 2: Actualización incremental
```
Situación: Importaste nuevo Excel, 50 fotos nuevas

1. python tools\buscador_de_fotos_retail.py --auto
   → Copia solo 50 faltantes

2. python tools\convertir_miniaturas_retail.py
   → Procesa las 50 nuevas (no regenera existentes)

3. Subir nuevas a Storage
```

### Caso 3: Regenerar miniaturas
```
Situación: Cambiar calidad o tamaños

1. Borrar carpeta miniaturas/
   rm -r "C:\Users\hecto\Documents\Prg_locales\proyectos\miniaturas"

2. Regenerar
   python tools\convertir_miniaturas_retail.py --calidad 90

3. Resubir a Storage
```

---

## 📊 COMPARACIÓN TAMAÑOS

### Para Tablet Bazzar
```
Recomendado: thumb_200 (grid/listados) + thumb_400 (modal)
Evitar: Originales (muy pesados para móvil)
```

### Para Report
```
Recomendado: thumb_400 (tarjetas) + thumb_800 (zoom)
Opcional: Originales (solo si necesario)
```

### Ancho de banda
```
Original:   500 KB × 100 fotos = 50 MB
thumb_200:   20 KB × 100 fotos = 2 MB  (25× más rápido)
thumb_400:   45 KB × 100 fotos = 4.5 MB (11× más rápido)
```

---

## 🔗 SCRIPTS RELACIONADOS

| Script | Propósito |
|--------|-----------|
| `buscador_de_fotos.py` | Versión Sales (registro_ventas_general_v2) |
| `buscador_de_fotos_retail.py` | **Versión Retail** (registro_st_vt_rc_reposicion) |
| `convertir_miniaturas_retail.py` | **Generar thumbnails** optimizados |

---

**Fecha:** 2026-06-11  
**Responsable:** Claude Code  
**Validado por:** Director