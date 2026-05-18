import { Suspense } from 'react'
import { createClient } from '@/lib/supabase/server'
import { RimecCard, type RimecAgrupado, type RimecVariante, type RimecGrade } from './RimecCard'
import { FiltrosRimec } from './FiltrosRimec'

export const revalidate = 60

const BUCKET = `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/productos`

interface StockRimecRow {
  det_id:               number
  pp_id:                number | null
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
  lpn:                  number | null
  lpc03:                number | null
}

interface Props {
  searchParams: { marca?: string; pp?: string }
}

export default async function RimecPage({ searchParams }: Props) {
  const { marca: marcaFiltro, pp: ppFiltro } = searchParams

  const supabase = await createClient()

  /* Stock en tránsito + stock físico en paralelo */
  const [{ data: dataTransito, error: errTransito }, { data: dataBazar, error: errBazar }] =
    await Promise.all([
      supabase.from('v_stock_rimec').select('*').order('marca').order('linea_codigo').order('referencia_codigo'),
      supabase.from('v_stock_bazar_rimec').select('*').order('linea_codigo').order('referencia_codigo'),
    ])

  if (errTransito) console.error('[rimec/transito]', errTransito.message)
  if (errBazar)    console.error('[rimec/bazar]',    errBazar.message)

  const todosTransito = agruparProductos(dataTransito ?? [])
  const todosBazar    = agruparProductos(dataBazar    ?? [])

  /* Filtrar en tránsito */
  let productosTransito = todosTransito
  if (marcaFiltro) productosTransito = productosTransito.filter(p => p.marca.toLowerCase() === marcaFiltro.toLowerCase())
  if (ppFiltro)    productosTransito = productosTransito.filter(p => p.variantes.some(v => v.pp_nro === ppFiltro))

  /* Filtrar stock físico (no tiene pp_nro útil para filtrar) */
  let productosBazar = todosBazar
  if (marcaFiltro) productosBazar = productosBazar.filter(p => p.marca.toLowerCase() === marcaFiltro.toLowerCase())

  /* Datos para filtros (basado en tránsito) */
  const marcas = Array.from(new Set([...todosTransito, ...todosBazar].map(p => p.marca))).sort()

  const ppSet = new Map<string, { nro: string; proforma: string; eta: string | null }>()
  for (const row of (dataTransito ?? []) as StockRimecRow[]) {
    if (!ppSet.has(row.pp_nro))
      ppSet.set(row.pp_nro, { nro: row.pp_nro, proforma: row.proforma, eta: row.eta })
  }
  const pps = Array.from(ppSet.values()).sort((a, b) => a.nro.localeCompare(b.nro))

  const totalParesTransito = productosTransito.reduce((s, p) => s + p.variantes.reduce((sv, v) => sv + v.cantidad_pares, 0), 0)
  const totalParesBazar    = productosBazar.reduce((s, p) => s + p.variantes.reduce((sv, v) => sv + v.cantidad_pares, 0), 0)

  return (
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-10">

      <Suspense>
        <FiltrosRimec
          marcas={marcas}
          pps={pps}
          totalModelos={productosTransito.length + productosBazar.length}
          totalPares={totalParesTransito + totalParesBazar}
        />
      </Suspense>

      {/* ── STOCK FÍSICO (ARRIBADO) ── */}
      {productosBazar.length > 0 && (
        <section className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">✅</span>
            <div>
              <h2 className="font-extrabold text-lg" style={{ color: '#1E3A5F' }}>
                Stock Disponible — {productosBazar.length} modelo(s) · {totalParesBazar.toLocaleString()} pares
              </h2>
              <p className="text-xs text-slate-400">Mercadería arribada y lista para entregar</p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
            {productosBazar.map(p => <RimecCard key={`bazar-${p.key}`} producto={p} />)}
          </div>
        </section>
      )}

      {/* ── STOCK EN TRÁNSITO ── */}
      {productosTransito.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🚢</span>
            <div>
              <h2 className="font-extrabold text-lg" style={{ color: '#1E3A5F' }}>
                En Tránsito — {productosTransito.length} modelo(s) · {totalParesTransito.toLocaleString()} pares
              </h2>
              <p className="text-xs text-slate-400">Mercadería en camino — disponible para pre-venta</p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
            {productosTransito.map(p => <RimecCard key={`transito-${p.key}`} producto={p} />)}
          </div>
        </section>
      )}

      {productosTransito.length === 0 && productosBazar.length === 0 && (
        <div className="flex flex-col items-center justify-center py-40 text-center">
          <div className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl mb-5"
               style={{ backgroundColor: '#f1f5f9' }}>📦</div>
          <p className="font-extrabold text-xl mb-2" style={{ color: '#1E3A5F' }}>Sin resultados</p>
          <p className="text-sm text-slate-400 mb-6 max-w-xs">
            No hay stock con esos filtros.
          </p>
          <a href="/rimec"
             className="text-sm font-bold px-6 py-3 rounded-xl text-white transition-all hover:opacity-90"
             style={{ backgroundColor: '#F97316' }}>
            Ver todo el stock
          </a>
        </div>
      )}

    </div>
  )
}

/* ── Agrupación: linea + referencia + material → variantes de color/lote ── */
function agruparProductos(items: StockRimecRow[]): RimecAgrupado[] {
  const prodMap = new Map<string, RimecAgrupado>()

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

    /* Parsear grades_json → array ordenado */
    const gradesObj = item.grades_json ?? {}
    const grades: RimecGrade[] = Object.entries(gradesObj)
      .map(([codigo, qty_por_caja]) => ({
        codigo,
        pares: (qty_por_caja as number) * item.cantidad_cajas,
      }))
      .filter(g => g.pares > 0)
      .sort((a, b) => {
        const na = parseFloat(a.codigo.split('/')[0]) || 0
        const nb = parseFloat(b.codigo.split('/')[0]) || 0
        return na - nb
      })

    const variante: RimecVariante = {
      det_id:         item.det_id,
      pp_id:          item.pp_id,
      pp_nro:         item.pp_nro,
      eta:            item.eta,
      color_code:     item.color_code,
      color_nombre:   item.color_nombre,
      imagen_url:     `${BUCKET}/${item.linea_codigo}-${item.referencia_codigo}-${item.material_code}-${item.color_code}.jpg`,
      grades,
      cantidad_pares: item.cantidad_pares,
      cantidad_cajas: item.cantidad_cajas,
      lpn:            item.lpn,
      lpc03:          item.lpc03,
    }

    prodMap.get(prodKey)!.variantes.push(variante)
  }

  return Array.from(prodMap.values())
}
