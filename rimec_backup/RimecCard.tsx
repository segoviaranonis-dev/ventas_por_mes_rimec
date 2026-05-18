'use client'

import React, { useState } from 'react'
import { createPortal } from 'react-dom'

/* ── Tipos ── */
export interface RimecGrade {
  codigo: string
  pares: number
}

export interface RimecVariante {
  det_id: number
  pp_id: number | null
  pp_nro: string
  eta: string | null
  color_code: string
  color_nombre: string
  imagen_url: string
  grades: RimecGrade[]
  cantidad_pares: number
  cantidad_cajas: number
  lpn: number | null
  lpc03: number | null
}

export interface RimecAgrupado {
  key: string
  linea_codigo: string
  referencia_codigo: string
  nombre: string
  material_code: string
  material_descripcion: string
  marca: string
  variantes: RimecVariante[]
}

/* ── Paleta ── */
const NAVY   = '#1E3A5F'
const ORANGE = '#F97316'
const AMBER  = '#F59E0B'

/* ── Mapa de colores por nombre (portugués + español) ── */
const COLOR_MAP: [RegExp, string][] = [
  [/preto|negro/i,              '#1a1a1a'],
  [/branco|blanco|off\s?white/i,'#f5f5f0'],
  [/cinza|gris/i,               '#9e9e9e'],
  [/prata|plata|plateado/i,     '#b0bec5'],
  [/marrom|marrón|marron/i,     '#6d4c41'],
  [/caramelo|caramel/i,         '#c19a6b'],
  [/bege|beige/i,               '#e8d5b0'],
  [/creme|crema/i,              '#f5f0e0'],
  [/nude/i,                     '#e8c9a0'],
  [/natural/i,                  '#d4b896'],
  [/couro|cuero/i,              '#a0785a'],
  [/azul|blue/i,                '#1565c0'],
  [/navy|marino/i,              '#1e3a5f'],
  [/celeste/i,                  '#4fc3f7'],
  [/vermelho|rojo|red/i,        '#c62828'],
  [/bordo|burdeo/i,             '#880e4f'],
  [/rosa|pink/i,                '#f48fb1'],
  [/coral/i,                    '#ff7043'],
  [/laranja|naranja|orange/i,   '#ef6c00'],
  [/amarelo|amarillo|yellow/i,  '#f9a825'],
  [/dourado|dorado|oro/i,       '#ffd54f'],
  [/verde|green/i,              '#2e7d32'],
  [/oliva/i,                    '#827717'],
  [/violeta/i,                  '#7b1fa2'],
  [/lilas|lila/i,               '#ab47bc'],
  [/turquesa/i,                 '#00897b'],
  [/mostarda|mostaza/i,         '#c8a227'],
  [/chocolate/i,                '#4e2b0e'],
  [/taupe/i,                    '#9e8e7e'],
  [/camel/i,                    '#c19a6b'],
]

function hexDesdeNombre(nombre: string): string {
  for (const [re, hex] of COLOR_MAP) {
    if (re.test(nombre)) return hex
  }
  return '#CBD5E1'
}

/* ── Imagen con fallback estilizado ── */
function Imagen({ src, alt, fallbackText, className, style }: {
  src: string; alt: string; fallbackText: string; className?: string; style?: React.CSSProperties
}) {
  const [err, setErr] = useState(false)

  if (err) return (
    <div className={`w-full h-full flex flex-col items-center justify-center gap-1 ${className ?? ''}`}
         style={{ background: 'linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 100%)' }}>
      <span className="text-white/80 text-sm font-extrabold tracking-wide">{fallbackText}</span>
      <span className="text-white/30 text-[9px] font-bold uppercase tracking-widest">RIMEC</span>
    </div>
  )

  /* eslint-disable-next-line @next/next/no-img-element */
  return <img src={src} alt={alt} onError={() => setErr(true)} className={className} style={style} />
}

/* ── Lightbox ── */
function Lightbox({ producto: p, initialIdx, onClose }: {
  producto: RimecAgrupado; initialIdx: number; onClose: () => void
}) {
  const [idx, setIdx] = useState(initialIdx)
  const v = p.variantes[idx]
  const precio = v.lpn ? new Intl.NumberFormat('es-PY').format(v.lpn) : null

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft')  setIdx(i => (i - 1 + p.variantes.length) % p.variantes.length)
      if (e.key === 'ArrowRight') setIdx(i => (i + 1) % p.variantes.length)
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [onClose, p.variantes.length])

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ backgroundColor: 'rgba(15,23,42,0.88)', backdropFilter: 'blur(6px)' }}
         onClick={onClose}>
      <div className="relative flex flex-col bg-white rounded-2xl overflow-hidden w-full max-w-lg"
           style={{ maxHeight: '92vh', boxShadow: '0 25px 80px rgba(0,0,0,0.45)' }}
           onClick={e => e.stopPropagation()}>

        {/* Imagen */}
        <div className="relative flex-1 min-h-0"
             style={{ background: 'linear-gradient(135deg,#f8fafc,#eff6ff)', minHeight: 320 }}>
          <Imagen src={v.imagen_url}
                  alt={`${p.linea_codigo}-${p.referencia_codigo}`}
                  fallbackText={`${p.linea_codigo}·${p.referencia_codigo}`}
                  className="w-full h-full object-contain"
                  style={{ maxHeight: 420 } as React.CSSProperties} />

          <button onClick={onClose}
                  className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full bg-white/90 hover:bg-white shadow"
                  style={{ color: '#64748b' }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {p.variantes.length > 1 && (
            <>
              <button onClick={() => setIdx(i => (i - 1 + p.variantes.length) % p.variantes.length)}
                      className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/90 hover:bg-white shadow"
                      style={{ color: NAVY }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button onClick={() => setIdx(i => (i + 1) % p.variantes.length)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/90 hover:bg-white shadow"
                      style={{ color: NAVY }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </>
          )}

          <div className="absolute top-3 left-3 flex flex-col gap-1">
            <span className="text-white text-[9px] font-extrabold px-2.5 py-1 rounded-full uppercase tracking-widest shadow-sm"
                  style={{ backgroundColor: NAVY }}>{p.marca}</span>
            <span className="text-white text-[8px] font-bold px-2 py-0.5 rounded-full uppercase"
                  style={{ backgroundColor: AMBER }}>🚢 tránsito</span>
          </div>

          {p.variantes.length > 1 && (
            <div className="absolute bottom-3 right-3 text-[10px] font-bold px-2 py-0.5 rounded-full"
                 style={{ backgroundColor: 'rgba(255,255,255,0.9)', color: '#475569' }}>
              {idx + 1} / {p.variantes.length}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="px-4 py-3 border-t border-slate-100">
          <div className="flex items-start justify-between gap-2 mb-3">
            <div>
              <div className="flex items-center gap-1">
                <span className="text-sm font-extrabold" style={{ color: NAVY }}>{p.linea_codigo}</span>
                <span className="text-slate-300">·</span>
                <span className="text-sm font-extrabold" style={{ color: ORANGE }}>{p.referencia_codigo}</span>
              </div>
              <p className="text-[11px] font-semibold mt-0.5" style={{ color: '#475569' }}>{p.nombre}</p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                {p.material_descripcion} · {v.color_nombre}
              </p>
              {v.eta && (
                <p className="text-[10px] font-semibold mt-1" style={{ color: AMBER }}>
                  🚢 ETA {v.eta.slice(0, 10)} · {v.pp_nro}
                </p>
              )}
            </div>
            {precio && (
              <div className="text-right shrink-0">
                <span className="text-[9px] font-semibold uppercase" style={{ color: '#94a3b8' }}>LPN Gs.</span>
                <div className="text-base font-extrabold" style={{ color: ORANGE }}>{precio}</div>
                <div className="text-[9px]" style={{ color: '#94a3b8' }}>{v.cantidad_pares} pares</div>
              </div>
            )}
          </div>

          {/* Swatches */}
          {p.variantes.length > 1 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {p.variantes.map((vv, i) => {
                const hex = hexDesdeNombre(vv.color_nombre)
                const isActive = i === idx
                return (
                  <button key={vv.det_id} onClick={() => setIdx(i)} title={vv.color_nombre}
                          style={{
                            width: 22, height: 22, borderRadius: '50%',
                            backgroundColor: hex,
                            border: isActive ? `2px solid ${ORANGE}` : '2px solid transparent',
                            outline: isActive ? `2px solid ${ORANGE}40` : '2px solid transparent',
                            outlineOffset: 1,
                            transform: isActive ? 'scale(1.2)' : 'scale(1)',
                            transition: 'all 0.15s ease',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                          }} />
                )
              })}
            </div>
          )}

          {/* Grades en lightbox */}
          <div className="flex flex-wrap gap-1.5">
            {v.grades.map(g => (
              <div key={g.codigo}
                   style={{
                     padding: '4px 10px', borderRadius: 8,
                     border: `1px solid #e2e8f0`,
                     backgroundColor: '#f8fafc',
                     textAlign: 'center',
                   }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: NAVY }}>{g.codigo}</div>
                <div style={{ fontSize: 9, fontWeight: 700, color: AMBER }}>{g.pares}p</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}

/* ── Card principal ── */
export function RimecCard({ producto: p }: { producto: RimecAgrupado }) {
  const [varIdx,   setVarIdx]  = useState(0)
  const [lightbox, setLightbox] = useState(false)

  const v      = p.variantes[varIdx]
  const precio = v.lpn ? new Intl.NumberFormat('es-PY').format(v.lpn) : null
  const etaStr = v.eta ? v.eta.slice(0, 10) : null

  return (
    <>
      <div className="group flex flex-col bg-white rounded-2xl overflow-hidden"
           style={{
             boxShadow: '0 2px 12px rgba(30,58,95,0.08)',
             border: '1px solid rgba(226,232,240,0.8)',
             transition: 'box-shadow 0.3s ease, transform 0.3s ease',
           }}
           onMouseEnter={e => {
             e.currentTarget.style.boxShadow = '0 12px 36px rgba(30,58,95,0.16)'
             e.currentTarget.style.transform = 'translateY(-2px)'
           }}
           onMouseLeave={e => {
             e.currentTarget.style.boxShadow = '0 2px 12px rgba(30,58,95,0.08)'
             e.currentTarget.style.transform = 'translateY(0)'
           }}>

        {/* ── Imagen ── */}
        <div className="relative aspect-square overflow-hidden cursor-zoom-in"
             style={{ background: 'linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)' }}
             onClick={() => setLightbox(true)}>
          <Imagen src={v.imagen_url}
                  alt={`${p.linea_codigo}-${p.referencia_codigo} ${v.color_nombre}`}
                  fallbackText={`${p.linea_codigo}·${p.referencia_codigo}`}
                  className="w-full h-full object-contain p-3 transition-transform duration-700 ease-out group-hover:scale-105" />

          {/* Lupa */}
          <div className="absolute bottom-2 right-2 w-7 h-7 flex items-center justify-center rounded-full bg-white/80 opacity-0 group-hover:opacity-100 transition-opacity shadow"
               style={{ color: NAVY }}>
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          {/* Badges */}
          <div className="absolute top-2.5 left-2.5 flex flex-col gap-1">
            <span className="text-white text-[9px] font-extrabold px-2.5 py-1 rounded-full uppercase tracking-widest shadow-sm"
                  style={{ backgroundColor: NAVY }}>
              {p.marca}
            </span>
            <span className="text-white text-[8px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide"
                  style={{ backgroundColor: AMBER }}>
              tránsito
            </span>
          </div>

          {p.variantes.length > 1 && (
            <span className="absolute top-2.5 right-2.5 text-[9px] font-bold px-1.5 py-0.5 rounded-full"
                  style={{ backgroundColor: 'rgba(255,255,255,0.92)', color: '#475569',
                           boxShadow: '0 1px 4px rgba(0,0,0,0.1)' }}>
              {p.variantes.length} col.
            </span>
          )}
        </div>

        {/* ── Info ── */}
        <div className="flex flex-col flex-1 p-3 gap-2">

          {/* Línea · Ref · Nombre */}
          <div>
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-[11px] font-extrabold tracking-wide" style={{ color: NAVY }}>
                {p.linea_codigo}
              </span>
              <span className="text-slate-300 text-[11px]">·</span>
              <span className="text-[11px] font-extrabold" style={{ color: ORANGE }}>
                {p.referencia_codigo}
              </span>
            </div>
            {p.nombre && (
              <p className="text-[10px] font-semibold mt-0.5 truncate" style={{ color: '#374151' }}>
                {p.nombre}
              </p>
            )}
            <p className="text-[10px] text-slate-400 mt-0.5 truncate">
              {p.material_descripcion} · {v.color_nombre}
            </p>
          </div>

          {/* Precio + pares */}
          <div className="flex items-center justify-between">
            {precio ? (
              <div>
                <span className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: '#94a3b8' }}>
                  LPN Gs.
                </span>
                {' '}
                <span className="text-sm font-extrabold" style={{ color: ORANGE }}>{precio}</span>
              </div>
            ) : (
              <span className="text-xs font-semibold" style={{ color: '#94a3b8' }}>Sin precio</span>
            )}
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md"
                  style={{ backgroundColor: '#fffbeb', color: AMBER }}>
              {v.cantidad_pares.toLocaleString('es-PY')} p
            </span>
          </div>

          {/* ETA */}
          {etaStr && (
            <p className="text-[9px] font-semibold truncate" style={{ color: '#64748b' }}>
              🚢 {etaStr} · {v.pp_nro}
            </p>
          )}

          {/* Swatches */}
          {p.variantes.length > 1 && (
            <div className="flex flex-wrap gap-1 pt-1.5 border-t" style={{ borderColor: '#f1f5f9' }}>
              {p.variantes.map((vv, i) => {
                const hex = hexDesdeNombre(vv.color_nombre)
                const isActive = i === varIdx
                return (
                  <button key={vv.det_id} onClick={() => setVarIdx(i)} title={vv.color_nombre}
                          style={{
                            width: 20, height: 20, borderRadius: '50%',
                            backgroundColor: hex,
                            border: isActive ? `2px solid ${ORANGE}` : '2px solid transparent',
                            outline: isActive ? `2px solid ${ORANGE}40` : '2px solid transparent',
                            outlineOffset: 1,
                            transform: isActive ? 'scale(1.15)' : 'scale(1)',
                            transition: 'all 0.15s ease',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                            cursor: 'pointer',
                          }} />
                )
              })}
            </div>
          )}

          {/* Grades */}
          <div className="flex flex-wrap gap-1">
            {v.grades.map(g => (
              <div key={g.codigo}
                   style={{
                     fontSize: 10, fontWeight: 700,
                     padding: '3px 6px', borderRadius: 6,
                     border: '1px solid #e2e8f0',
                     backgroundColor: '#f8fafc',
                     textAlign: 'center', minWidth: 28,
                   }}>
                <div style={{ color: NAVY }}>{g.codigo}</div>
                <div style={{ fontSize: 8, color: AMBER, fontWeight: 800 }}>{g.pares}</div>
              </div>
            ))}
          </div>

        </div>
      </div>

      {lightbox && (
        <Lightbox producto={p} initialIdx={varIdx} onClose={() => setLightbox(false)} />
      )}
    </>
  )
}
