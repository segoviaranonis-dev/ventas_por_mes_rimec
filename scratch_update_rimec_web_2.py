import os

catalogo_content = """'use client'

import React, { useState } from 'react'
import { createPortal } from 'react-dom'
import { useSesion } from '@/store/sesion'
import { DialogoActivacion } from '@/components/DialogoActivacion'
import { HeaderSesion } from '@/components/HeaderSesion'
import { formatearQuincena } from '@/lib/utils'

export interface RimecVariante {
  det_id: number
  pp_nro: string
  eta: string | null
  color_code: string
  color_nombre: string
  imagen_url: string
  cantidad_cajas: number
  pares_por_caja: number
  cajas_disponibles: number
  lpn: number | null
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

const AZUL = '#1E3A8A'
const CELESTE = '#0EA5E9'

const COLOR_MAP: [RegExp, string][] = [
  [/preto|negro/i,              '#1a1a1a'],
  [/branco|blanco|off\\s?white/i,'#f5f5f0'],
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

function Imagen({ src, alt, fallbackText, className, style }: {
  src: string; alt: string; fallbackText: string; className?: string; style?: React.CSSProperties
}) {
  const [err, setErr] = useState(false)
  if (err) return (
    <div className={`w-full h-full flex flex-col items-center justify-center gap-1 ${className ?? ''}`}
         style={{ background: `linear-gradient(135deg, ${AZUL} 0%, #2d5a8e 100%)` }}>
      <span className="text-white/80 text-sm font-extrabold tracking-wide">{fallbackText}</span>
      <span className="text-white/30 text-[9px] font-bold uppercase tracking-widest">RIMEC</span>
    </div>
  )
  return <img src={src} alt={alt} onError={() => setErr(true)} className={className} style={style} />
}

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
                      style={{ color: AZUL }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button onClick={() => setIdx(i => (i + 1) % p.variantes.length)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full bg-white/90 hover:bg-white shadow"
                      style={{ color: AZUL }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </>
          )}

          <div className="absolute top-3 left-3 flex flex-col gap-1">
            <span className="text-white text-[9px] font-extrabold px-2.5 py-1 rounded-full uppercase tracking-widest shadow-sm"
                  style={{ backgroundColor: AZUL }}>{p.marca}</span>
            <span className="text-white text-[8px] font-bold px-2 py-0.5 rounded-full uppercase"
                  style={{ backgroundColor: CELESTE }}>tránsito</span>
          </div>
        </div>

        <div className="px-4 py-3 border-t border-slate-100">
          <div className="flex items-start justify-between gap-2 mb-3">
            <div>
              <div className="flex items-center gap-1 flex-wrap">
                <span className="text-sm font-extrabold" style={{ color: AZUL }}>{p.linea_codigo}</span>
                <span className="text-slate-300">·</span>
                <span className="text-sm font-extrabold" style={{ color: CELESTE }}>{p.referencia_codigo}</span>
              </div>
              <p className="text-[11px] font-semibold mt-0.5" style={{ color: '#475569' }}>{p.nombre}</p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                {p.material_descripcion} · {v.color_nombre}
              </p>
              {v.eta && (
                <p className="text-[10px] font-semibold mt-1" style={{ color: CELESTE }}>
                  🚢 ETA {v.eta.slice(0, 10)} · {v.pp_nro}
                </p>
              )}
            </div>
            {precio && (
              <div className="text-right shrink-0">
                <span className="text-[9px] font-semibold uppercase" style={{ color: '#94a3b8' }}>LPN Gs.</span>
                <div className="text-base font-extrabold" style={{ color: CELESTE }}>{precio}</div>
                <div className="text-[9px]" style={{ color: '#94a3b8' }}>disp: {v.cajas_disponibles} cjs</div>
              </div>
            )}
          </div>
          
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
                            border: isActive ? `2px solid ${CELESTE}` : '2px solid transparent',
                            outline: isActive ? `2px solid ${CELESTE}40` : '2px solid transparent',
                            outlineOffset: 1,
                            transform: isActive ? 'scale(1.2)' : 'scale(1)',
                            transition: 'all 0.15s ease',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                          }} />
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}

function TarjetaProducto({ producto: p, onNeedSession }: { producto: RimecAgrupado; onNeedSession: () => void }) {
  const [varIdx, setVarIdx] = useState(0)
  const [lightbox, setLightbox] = useState(false)
  
  const { activa, carrito, tienePrecio, agregarCaja, quitarCaja } = useSesion()

  const v = p.variantes[varIdx]
  const precio = v.lpn ? new Intl.NumberFormat('es-PY').format(v.lpn) : null
  const etaStr = v.eta ? v.eta.slice(0, 10) : null
  
  const cartItem = carrito[v.det_id]
  const cajas = cartItem ? cartItem.cajas : 0
  const maxCajas = v.cajas_disponibles
  const puedeAgregar = activa && tienePrecio && cajas < maxCajas
  const botonPlusColor = !activa ? '#CBD5E1' : !tienePrecio ? '#F1F5F9' : cajas >= maxCajas ? '#E2E8F0' : AZUL
  const botonPlusTxt = !activa ? 'white' : !tienePrecio ? '#CBD5E1' : cajas >= maxCajas ? '#94A3B8' : 'white'

  const handleAgregar = () => {
    if (!activa) { onNeedSession(); return }
    if (!tienePrecio || cajas >= maxCajas) return
    agregarCaja({
      det_id: v.det_id,
      marca: p.marca,
      linea_codigo: p.linea_codigo,
      referencia_codigo: p.referencia_codigo,
      material_descripcion: p.material_descripcion,
      color_nombre: v.color_nombre,
      cajas: 1,
      pares_por_caja: v.pares_por_caja,
      precio_unitario: v.lpn ?? 0,
      eta: v.eta
    })
  }

  return (
    <>
      <div className="group flex flex-col bg-white rounded-2xl overflow-hidden h-full"
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

        <div className="relative aspect-square overflow-hidden cursor-zoom-in"
             style={{ background: 'linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)' }}
             onClick={() => setLightbox(true)}>
          <Imagen src={v.imagen_url}
                  alt={`${p.linea_codigo}-${p.referencia_codigo} ${v.color_nombre}`}
                  fallbackText={`${p.linea_codigo}·${p.referencia_codigo}`}
                  className="w-full h-full object-contain p-3 transition-transform duration-700 ease-out group-hover:scale-105" />

          <div className="absolute bottom-2 right-2 w-7 h-7 flex items-center justify-center rounded-full bg-white/80 opacity-0 group-hover:opacity-100 transition-opacity shadow"
               style={{ color: AZUL }}>
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <div className="absolute top-2.5 left-2.5 flex flex-col gap-1">
            <span className="text-white text-[9px] font-extrabold px-2.5 py-1 rounded-full uppercase tracking-widest shadow-sm"
                  style={{ backgroundColor: AZUL }}>
              {p.marca}
            </span>
            <span className="text-white text-[8px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide"
                  style={{ backgroundColor: CELESTE }}>
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

        <div className="flex flex-col flex-1 p-3 gap-2">

          <div>
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-[11px] font-extrabold tracking-wide" style={{ color: AZUL }}>
                {p.linea_codigo}
              </span>
              <span className="text-slate-300 text-[11px]">·</span>
              <span className="text-[11px] font-extrabold" style={{ color: CELESTE }}>
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

          <div className="flex items-center justify-between">
            {!activa ? (
              <span className="text-xs font-semibold" style={{ color: '#94a3b8' }}>🔒 Inicie sesión</span>
            ) : precio ? (
              <div>
                <span className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: '#94a3b8' }}>
                  LPN Gs.
                </span>
                {' '}
                <span className="text-sm font-extrabold" style={{ color: CELESTE }}>{precio}</span>
              </div>
            ) : (
              <span className="text-xs font-semibold" style={{ color: '#94a3b8' }}>Sin precio</span>
            )}
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md"
                  style={{ backgroundColor: '#f0f9ff', color: CELESTE }}>
              disp: {v.cajas_disponibles} cjs
            </span>
          </div>

          {etaStr && (
            <p className="text-[9px] font-semibold truncate" style={{ color: '#64748b' }}>
              🚢 {etaStr} · {v.pp_nro}
            </p>
          )}

          {p.variantes.length > 1 && (
            <div className="flex flex-wrap gap-1 pt-1.5 border-t mt-1" style={{ borderColor: '#f1f5f9' }}>
              {p.variantes.map((vv, i) => {
                const hex = hexDesdeNombre(vv.color_nombre)
                const isActive = i === varIdx
                return (
                  <button key={vv.det_id} onClick={() => setVarIdx(i)} title={vv.color_nombre}
                          style={{
                            width: 20, height: 20, borderRadius: '50%',
                            backgroundColor: hex,
                            border: isActive ? `2px solid ${CELESTE}` : '2px solid transparent',
                            outline: isActive ? `2px solid ${CELESTE}40` : '2px solid transparent',
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 'auto', paddingTop: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                onClick={() => { if (!activa) { onNeedSession(); return }; quitarCaja(v.det_id) }}
                disabled={!activa || cajas === 0}
                style={{
                  width: 38, height: 38, borderRadius: '50%',
                  border: `2px solid ${activa && cajas > 0 ? AZUL : '#E2E8F0'}`,
                  backgroundColor: 'white', color: activa && cajas > 0 ? AZUL : '#CBD5E1',
                  fontSize: 20, fontWeight: 700, cursor: activa && cajas > 0 ? 'pointer' : 'not-allowed',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>−</button>

              <div style={{ flex: 1, textAlign: 'center' }}>
                <p style={{ fontSize: 20, fontWeight: 900, color: activa && tienePrecio ? AZUL : '#CBD5E1', lineHeight: 1 }}>{cajas}</p>
                <p style={{ fontSize: 10, color: '#64748B', marginTop: 2 }}>
                  {cajas === 0 ? 'cajas' : `= ${cajas * v.pares_por_caja} p`}
                </p>
              </div>

              <button
                onClick={handleAgregar}
                disabled={!puedeAgregar}
                title={!activa ? 'Iniciá sesión' : !tienePrecio ? 'Sin precio en esta lista' : cajas >= maxCajas ? 'Máximo alcanzado' : ''}
                style={{
                  width: 38, height: 38, borderRadius: '50%',
                  border: `2px solid ${botonPlusColor}`,
                  backgroundColor: botonPlusColor,
                  color: botonPlusTxt,
                  fontSize: 20, fontWeight: 700, cursor: puedeAgregar ? 'pointer' : 'not-allowed',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>+</button>
            </div>

            <p style={{ fontSize: 10, textAlign: 'center', color: '#94A3B8' }}>
              {v.pares_por_caja} pares/caja · máx. {maxCajas} cjs
            </p>
            {cajas > 0 && (
              <a href="/carrito" style={{
                display: 'block', width: '100%', padding: '8px 0', borderRadius: 8,
                backgroundColor: '#10B981', color: 'white', textAlign: 'center',
                fontWeight: 700, fontSize: 13, cursor: 'pointer', border: 'none',
                textDecoration: 'none', marginTop: 4,
              }}>
                En pedido ✅ →
              </a>
            )}
          </div>

        </div>
      </div>

      {lightbox && (
        <Lightbox producto={p} initialIdx={varIdx} onClose={() => setLightbox(false)} />
      )}
    </>
  )
}

function Pill({ active, onClick, children }: { active: boolean, onClick: () => void, children: React.ReactNode }) {
  return (
    <button onClick={onClick} style={{
      padding: '6px 14px', borderRadius: 20, fontSize: 13, fontWeight: 600, cursor: 'pointer', border: 'none',
      backgroundColor: active ? AZUL : '#E2E8F0',
      color: active ? 'white' : '#475569',
      transition: 'all 0.2s',
    }}>
      {children}
    </button>
  )
}

export function CatalogoGrid({ productos, marcas, pps }: { productos: RimecAgrupado[], marcas: string[], pps: any[] }) {
  const { activa, carrito } = useSesion()
  const [marcaFiltro, setMarcaFiltro] = useState('')
  const [ppFiltro, setPpFiltro] = useState('')
  const [buscar, setBuscar] = useState('')
  const [mostrarDialogo, setMostrarDialogo] = useState(false)

  const filtered = productos.filter(p => {
    if (marcaFiltro && p.marca !== marcaFiltro) return false
    if (ppFiltro && !p.variantes.some(v => v.pp_nro === ppFiltro)) return false
    if (buscar) {
      const q = buscar.toLowerCase()
      if (![p.marca, p.linea_codigo, p.referencia_codigo, p.nombre, p.material_descripcion]
            .some(f => f?.toLowerCase().includes(q)) &&
          !p.variantes.some(v => v.color_nombre.toLowerCase().includes(q))) return false
    }
    return true
  })

  const cartItems = Object.values(carrito)
  const totalCajas = cartItems.reduce((s, i) => s + i.cajas, 0)
  const totalPares = cartItems.reduce((s, i) => s + i.pares, 0)
  const cartCount = cartItems.length

  return (
    <>
      <DialogoActivacion open={mostrarDialogo} onClose={() => setMostrarDialogo(false)} />
      <HeaderSesion />

      <div style={{ backgroundColor: '#F8FAFC', borderRadius: 16, padding: 20, marginBottom: 28,
                    border: '1px solid #E2E8F0' }}>
        <input value={buscar} onChange={e => setBuscar(e.target.value)}
          placeholder="Buscar por marca, línea, referencia, color..."
          style={{
            width: '100%', padding: '12px 16px', borderRadius: 10,
            border: '2px solid #E2E8F0', fontSize: 16, color: '#1E293B',
            backgroundColor: 'white', marginBottom: 14, boxSizing: 'border-box', outline: 'none',
          }} />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
          <Pill active={!marcaFiltro} onClick={() => setMarcaFiltro('')}>Todas las marcas</Pill>
          {marcas.map(m => (
            <Pill key={m} active={marcaFiltro === m} onClick={() => setMarcaFiltro(marcaFiltro === m ? '' : m)}>
              {m}
            </Pill>
          ))}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Pill active={!ppFiltro} onClick={() => setPpFiltro('')}>Todos los lotes</Pill>
          {pps.map(p => (
            <Pill key={p.nro} active={ppFiltro === p.nro} onClick={() => setPpFiltro(ppFiltro === p.nro ? '' : p.nro)}>
              {p.nro}{p.eta ? ` · ${formatearQuincena(p.eta)}` : ''}
            </Pill>
          ))}
        </div>
      </div>

      <p style={{ fontSize: 14, color: '#64748B', marginBottom: 20 }}>
        Mostrando <strong style={{ color: AZUL }}>{filtered.length}</strong> modelos
        {!activa && (
          <span style={{ marginLeft: 12, color: CELESTE, fontWeight: 600 }}>
            🔒 Los precios se muestran al iniciar sesión
          </span>
        )}
      </p>

      {!activa && (
        <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 50 }}>
          <button onClick={() => setMostrarDialogo(true)} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '16px 28px', borderRadius: 16,
            backgroundColor: AZUL, color: 'white',
            fontWeight: 700, fontSize: 16, border: 'none', cursor: 'pointer',
            boxShadow: '0 8px 28px rgba(30,64,175,0.45)',
          }}>
            🔑 Iniciar sesión
          </button>
        </div>
      )}
      {activa && cartCount > 0 && (
        <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 50 }}>
          <a href="/carrito" style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '16px 28px', borderRadius: 16,
            backgroundColor: AZUL, color: 'white',
            fontWeight: 700, fontSize: 16, textDecoration: 'none',
            boxShadow: '0 8px 28px rgba(30,64,175,0.45)',
          }}>
            🛒 {cartCount} ref · {totalCajas} cajas · {totalPares.toLocaleString('es-PY')} pares
          </a>
        </div>
      )}

      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <p style={{ fontSize: 48, marginBottom: 12 }}>📦</p>
          <p style={{ fontSize: 18, fontWeight: 700, color: '#94A3B8' }}>Sin resultados</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
          {filtered.map(p => (
            <TarjetaProducto key={p.key} producto={p} onNeedSession={() => setMostrarDialogo(true)} />
          ))}
        </div>
      )}
    </>
  )
}
"""

with open(r"C:\Users\hecto\Documents\Prg_locales\rimec-web\app\CatalogoGrid.tsx", "w", encoding="utf-8") as f:
    f.write(catalogo_content)

print("Updated CatalogoGrid.tsx")
