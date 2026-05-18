'use client'

import { useRouter, useSearchParams } from 'next/navigation'

interface Props {
  marcas:       string[]
  pps:          { nro: string; proforma: string; eta: string | null }[]
  totalModelos: number
  totalPares:   number
}

const NAVY   = '#1E3A5F'
const ORANGE = '#F97316'
const AMBER  = '#F59E0B'

export function FiltrosRimec({ marcas, pps, totalModelos, totalPares }: Props) {
  const router       = useRouter()
  const searchParams = useSearchParams()

  const marcaActual = searchParams.get('marca') ?? ''
  const ppActual    = searchParams.get('pp')    ?? ''

  function aplicar(opts: { marca?: string; pp?: string }) {
    const params = new URLSearchParams()
    const m = opts.marca !== undefined ? opts.marca : marcaActual
    const p = opts.pp    !== undefined ? opts.pp    : ppActual
    if (m) params.set('marca', m)
    if (p) params.set('pp',    p)
    router.push(`/rimec${params.toString() ? '?' + params.toString() : ''}`)
  }

  const hayFiltros = !!(marcaActual || ppActual)

  return (
    <div className="mb-8">

      {/* ── Encabezado ── */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight" style={{ color: NAVY }}>
              {marcaActual
                ? marcaActual.charAt(0) + marcaActual.slice(1).toLowerCase()
                : 'Stock en Tránsito'}
            </h1>
            <span className="px-3 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-widest text-white"
                  style={{ backgroundColor: AMBER }}>
              🚢 Rimec
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-sm font-semibold" style={{ color: ORANGE }}>
              {totalModelos.toLocaleString('es-PY')} modelos
            </span>
            <span className="w-1 h-1 rounded-full bg-slate-300" />
            <span className="text-sm text-slate-400">
              {totalPares.toLocaleString('es-PY')} pares en camino
            </span>
          </div>
        </div>

        {hayFiltros && (
          <button onClick={() => router.push('/rimec')}
                  className="flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-xl border transition-all hover:border-red-300 hover:text-red-500 hover:bg-red-50"
                  style={{ borderColor: '#e2e8f0', color: '#94a3b8' }}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Limpiar filtros
          </button>
        )}
      </div>

      {/* ── Barra de filtros ── */}
      <div className="bg-white rounded-2xl p-4 space-y-4"
           style={{ boxShadow: '0 2px 16px rgba(30,58,95,0.07)', border: '1px solid #f1f5f9' }}>

        {/* Marcas */}
        <div className="flex items-start gap-3 flex-wrap">
          <span className="text-[10px] font-bold uppercase tracking-widest shrink-0 mt-1"
                style={{ color: '#94a3b8', minWidth: 44 }}>Marca</span>
          <div className="flex flex-wrap gap-1.5">
            <MarcaPill active={!marcaActual} onClick={() => aplicar({ marca: '' })}>
              Todas
            </MarcaPill>
            {marcas.map(m => (
              <MarcaPill key={m} active={marcaActual === m}
                         onClick={() => aplicar({ marca: marcaActual === m ? '' : m })}>
                {m}
              </MarcaPill>
            ))}
          </div>
        </div>

        {/* Separador */}
        <div className="h-px" style={{ backgroundColor: '#f1f5f9' }} />

        {/* Lotes / PPs */}
        <div className="flex items-start gap-3 flex-wrap">
          <span className="text-[10px] font-bold uppercase tracking-widest shrink-0 mt-1"
                style={{ color: '#94a3b8', minWidth: 44 }}>Lote</span>
          <div className="flex flex-wrap gap-1.5">
            <LotePill active={!ppActual} onClick={() => aplicar({ pp: '' })}>
              Todos
            </LotePill>
            {pps.map(pp => (
              <LotePill key={pp.nro} active={ppActual === pp.nro}
                        onClick={() => aplicar({ pp: ppActual === pp.nro ? '' : pp.nro })}>
                {pp.nro}
                {pp.eta && (
                  <span className="ml-1 opacity-70">· {pp.eta.slice(0, 10)}</span>
                )}
              </LotePill>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

/* ── Pills ── */
function MarcaPill({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button onClick={onClick}
            className="px-4 py-1.5 rounded-full text-xs font-bold transition-all duration-150"
            style={active
              ? { backgroundColor: NAVY, color: 'white', boxShadow: '0 2px 8px rgba(30,58,95,0.25)' }
              : { backgroundColor: '#f1f5f9', color: '#64748b' }}
            onMouseEnter={e => { if (!active) e.currentTarget.style.backgroundColor = '#e2e8f0' }}
            onMouseLeave={e => { if (!active) e.currentTarget.style.backgroundColor = '#f1f5f9' }}>
      {children}
    </button>
  )
}

function LotePill({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button onClick={onClick}
            className="px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-150"
            style={active
              ? { backgroundColor: AMBER, color: 'white', boxShadow: '0 2px 8px rgba(245,158,11,0.3)' }
              : { backgroundColor: 'white', color: '#64748b', border: '1.5px solid #e2e8f0' }}
            onMouseEnter={e => {
              if (!active) { e.currentTarget.style.borderColor = AMBER; e.currentTarget.style.color = AMBER }
            }}
            onMouseLeave={e => {
              if (!active) { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#64748b' }
            }}>
      {children}
    </button>
  )
}
