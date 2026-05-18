import os
import re

file_path = r"C:\Users\hecto\Documents\Prg_locales\rimec-web\app\CatalogoGrid.tsx"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("import { useSesion } from '@/store/sesion'", "import { useSesion } from '@/store/sesionVenta'")
content = content.replace("import { formatearQuincena } from '@/lib/utils'", "import { formatearQuincena } from '@/lib/fecha'")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed imports in CatalogoGrid.tsx")
