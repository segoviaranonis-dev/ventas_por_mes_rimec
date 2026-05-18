import os
import re

file_path = r"C:\Users\hecto\Documents\Prg_locales\rimec-web\app\CatalogoGrid.tsx"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the import
content = content.replace("import { HeaderSesion } from '@/components/HeaderSesion'", "")

# Add the HeaderSesion function definition before CatalogoGrid
header_sesion_code = """
function HeaderSesion() {
  const { activa, user, cerrarSesion } = useSesion()

  if (!activa) return null

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 20px', backgroundColor: AZUL, color: 'white',
      borderRadius: 16, marginBottom: 28, boxShadow: '0 4px 12px rgba(30,64,175,0.2)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: 'white', color: AZUL, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>
          {user?.charAt(0).toUpperCase() || 'U'}
        </div>
        <div>
          <p style={{ fontSize: 14, fontWeight: 700 }}>{user}</p>
          <p style={{ fontSize: 11, color: '#93C5FD' }}>Sesión activa</p>
        </div>
      </div>
      <button onClick={cerrarSesion} style={{
        padding: '8px 16px', borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.1)', color: 'white',
        border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600
      }}>
        Cerrar sesión
      </button>
    </div>
  )
}
"""

content = content.replace("export function CatalogoGrid", header_sesion_code + "\nexport function CatalogoGrid")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed CatalogoGrid.tsx")
