import os

file_path = r"C:\Users\hecto\Documents\Prg_locales\rimec-web\app\CatalogoGrid.tsx"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_code = """function HeaderSesion() {
  const { activa, user, cerrarSesion } = useSesion(s => ({
    activa: s.activa,
    user: s.vendedor?.descp_vendedor || s.cliente?.descp_cliente,
    cerrarSesion: s.desactivar
  }))"""

new_code = """function HeaderSesion() {
  const activa = useSesion(s => s.activa)
  const vendedorDesc = useSesion(s => s.vendedor?.descp_vendedor)
  const clienteDesc = useSesion(s => s.cliente?.descp_cliente)
  const cerrarSesion = useSesion(s => s.desactivar)
  
  const user = vendedorDesc || clienteDesc"""

content = content.replace(old_code, new_code)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed HeaderSesion Zustand infinite loop")
