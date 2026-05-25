import os

page_content = """import { supabase } from '@/lib/supabase'
import { CatalogoGrid } from './CatalogoGrid'

export const revalidate = 60

export interface StockRow {
  det_id:               number
  pp_id:                number
  pp_nro:               string
  proforma:             string
  eta:                  string | null
  marca:                string
  linea_codigo:         string
  referencia_codigo:    string
  nombre:               string
  material_code:        string
  material_descripcion: string
  color_code:           string
  color_nombre:         string
  grades_json:          Record<string, number> | null
  cantidad_cajas:       number
  cantidad_pares:       number
  pares_por_caja:       number
  pares_vendidos:       number
  pares_disponibles:    number
  cajas_disponibles:    number
  lpn:                  number | null
  lpc02:                number | null
  lpc03:                number | null
  lpc04:                number | null
}

const BUCKET = `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/productos`

function agruparProductos(items: StockRow[]) {
  const prodMap = new Map<string, any>()

  for (const item of items) {
    const prodKey = `${item.linea_codigo}-${item.referencia_codigo}-${item.material_code}`

    if (!prodMap.has(prodKey)) {
      prodMap.set(prodKey, {
        key:                  prodKey,
        linea_codigo:         item.linea_codigo,
        referencia_codigo:    item.referencia_codigo,
        nombre:               item.nombre,
        material_code:        item.material_code,
        material_descripcion: item.material_descripcion,
        marca:                item.marca,
        variantes:            [],
      })
    }
    
    // Generar gradas_fmt a partir de grades_json
    let gradas_fmt = ""
    if (item.grades_json) {
      const g = item.grades_json
      const keys = Object.keys(g).sort((a,b) => parseFloat(a.split('/')[0]) - parseFloat(b.split('/')[0]))
      if (keys.length > 0) {
        gradas_fmt = `${keys[0]}(${keys.map(k => g[k]).join('-')})${keys[keys.length-1]}`
      }
    }

    prodMap.get(prodKey)!.variantes.push({
      det_id:         item.det_id,
      pp_id:          item.pp_id,
      pp_nro:         item.pp_nro,
      eta:            item.eta,
      material_code:  item.material_code,
      color_code:     item.color_code,
      color_nombre:   item.color_nombre,
      gradas_fmt:     gradas_fmt,
      imagen_url:     `${BUCKET}/${item.linea_codigo}-${item.referencia_codigo}-${item.material_code}-${item.color_code}.jpg`,
      cantidad_cajas: item.cantidad_cajas,
      pares_por_caja: item.pares_por_caja,
      cajas_disponibles: item.cajas_disponibles,
      lpn:            item.lpn,
      lpc02:          item.lpc02,
      lpc03:          item.lpc03,
      lpc04:          item.lpc04,
    })
  }

  return Array.from(prodMap.values())
}

export default async function HomePage() {
  const { data, error } = await supabase
    .from('v_stock_rimec')
    .select('*')
    .order('marca')
    .order('linea_codigo')
    .order('referencia_codigo')

  if (error) console.error('[rimec-web]', error.message)

  const rows = (data ?? []) as StockRow[]
  const productos = agruparProductos(rows)
  const marcas = Array.from(new Set(rows.map(r => r.marca))).sort()
  const pps = Array.from(
    new Map(rows.map(r => [r.pp_nro, { nro: r.pp_nro, eta: r.eta }])).values()
  ).sort((a, b) => a.nro.localeCompare(b.nro))

  const totalPares = rows.reduce((s, r) => s + r.cantidad_pares, 0)

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-black tracking-tight mb-1" style={{ color: '#0EA5E9' }}>
          Stock Disponible
        </h1>
        <div className="flex items-center gap-4 text-sm" style={{ color: '#94A3B8' }}>
          <span style={{ color: '#0EA5E9', fontWeight: 700 }}>{productos.length} modelos</span>
          <span>·</span>
          <span>{totalPares.toLocaleString('es-PY')} pares en camino</span>
        </div>
      </div>
      <CatalogoGrid productos={productos} marcas={marcas} pps={pps} />
    </div>
  )
}
"""

with open(r"C:\Users\hecto\Documents\Prg_locales\rimec-web\app\page.tsx", "w", encoding="utf-8") as f:
    f.write(page_content)

print("Updated page.tsx with correct fields")
