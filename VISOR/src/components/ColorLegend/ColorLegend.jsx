import { useState, useEffect } from 'react'
import useStore from '../../store/useStore'
import { DBZ_LEGEND } from '../../config/radars'

/* ── Geometry derived from the 13-class scale (colours/ranges unchanged) ──
   Boundaries run bottom→top: 8,10,15,…,65,70 (14 values, 13 equal cells).
   Ticks and category anchors are positioned on these cell boundaries, so a
   tick at value V lands exactly on a colour-band edge.                     */
const LOWS = DBZ_LEGEND.map((it) => Number(it.range.split('-')[0]))
const TOP_VAL = Number(DBZ_LEGEND[DBZ_LEGEND.length - 1].range.split('-')[1]) // 70
const BOUNDARIES = [...LOWS, TOP_VAL] // [8,10,15,…,65,70]
const BASE_VAL = BOUNDARIES[0]        // 8 dBZ floor (below → transparent)
const NB = BOUNDARIES.length - 1      // 13 cells

/* % from the TOP of the bar for a boundary index (0 = bottom, NB = top) */
const topPctForIdx = (idx) => (1 - idx / NB) * 100

/* Numeric ticks: multiples of 10 that coincide with a band boundary */
const TICKS = [70, 60, 50, 40, 30, 20, 10]
  .map((v) => ({ v, idx: BOUNDARIES.indexOf(v) }))
  .filter((t) => t.idx >= 0)
  .map((t) => ({ v: t.v, top: topPctForIdx(t.idx) }))

/* Four rain-intensity categories, anchored at the centre of their band.
   a/b are boundary indices: ligera 8–25, moderada 25–40, fuerte 40–55,
   muy fuerte 55–70 dBZ.                                                    */
const CATEGORIES = [
  { l1: 'Lluvia', l2: 'muy fuerte', icon: 'fa-cloud-bolt',          a: 10, b: 13 },
  { l1: 'Lluvia', l2: 'fuerte',     icon: 'fa-cloud-showers-heavy', a: 7,  b: 10 },
  { l1: 'Lluvia', l2: 'moderada',   icon: 'fa-cloud-showers-water', a: 4,  b: 7  },
  { l1: 'Lluvia', l2: 'ligera',     icon: 'fa-cloud-rain',          a: 0,  b: 4  },
].map((c) => ({ ...c, top: topPctForIdx((c.a + c.b) / 2) }))

const BAR_H = 320 // px — tall enough for rotated category labels
const MOBILE_BAR_H = 200 // px — barra de escala compacta para móvil

/* Bar bottom→top = navy(8) → dark-red(70): reverse so highest dBZ on top */
const CELLS_TOP_DOWN = [...DBZ_LEGEND].reverse()

/* ── Desktop vertical panel ──────────────────────────── */
function DesktopLegend({ barHeight }) {
  const minimized = useStore((s) => s.legendMinimized)
  const setLegendMinimized = useStore((s) => s.setLegendMinimized)

  return (
    <div
      className="hidden sm:block fixed z-[999] text-white transition-all duration-200 left-2.5"
      style={{ bottom: `${barHeight + 20}px` }}
      role="region"
      aria-label="Leyenda de reflectividad dBZ"
    >
      <div className="bg-gray-950/90 backdrop-blur-sm rounded-lg shadow-xl border border-white/10
        overflow-hidden">

        {/* Toggle header */}
        <button
          onClick={() => setLegendMinimized(!minimized)}
          className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-semibold
            hover:bg-white/5 transition-colors touch-manipulation
            focus:outline-none focus:ring-2 focus:ring-blue-400/60 focus:ring-inset"
          aria-expanded={!minimized}
        >
          <span
            className="w-3 h-3 rounded-sm shrink-0 border border-black/20"
            style={{ background: `linear-gradient(135deg, ${DBZ_LEGEND[0].color}, ${DBZ_LEGEND[6].color}, ${DBZ_LEGEND[12].color})` }}
            aria-hidden="true"
          />
          <span className="text-gray-300">Reflectividad (dBZ)</span>
          <i className={`fas fa-chevron-${minimized ? 'up' : 'down'} text-[8px] text-gray-500 ml-auto`} />
        </button>

        {!minimized && (
          <div className="px-2.5 pb-2 pt-1">
            <div className="flex items-stretch" style={{ height: `${BAR_H}px` }}>

              {/* Category labels (rotated, two lines, left of the bar) */}
              <div className="relative shrink-0" style={{ width: '30px' }} aria-hidden="true">
                {CATEGORIES.map((c) => (
                  <div
                    key={c.l2}
                    className="absolute left-1/2 flex items-center gap-1
                      text-[8px] font-medium text-gray-200"
                    style={{ top: `${c.top}%`, transform: 'translate(-50%,-50%) rotate(-90deg)', transformOrigin: 'center' }}
                  >
                    <i className={`fas ${c.icon} text-[9px] text-gray-400`} />
                    <span className="flex flex-col items-center text-center leading-tight">
                      <span className="whitespace-nowrap">{c.l1}</span>
                      <span className="whitespace-nowrap">{c.l2}</span>
                    </span>
                  </div>
                ))}
              </div>

              {/* Classified colour bar */}
              <div
                className="shrink-0 overflow-hidden rounded-sm border border-black/40"
                style={{ width: '14px' }}
              >
                <div className="flex flex-col h-full">
                  {CELLS_TOP_DOWN.map((item) => (
                    <div key={item.range} style={{ flex: 1, backgroundColor: item.color }} />
                  ))}
                </div>
              </div>

              {/* Numeric ticks (right of the bar) */}
              <div className="relative shrink-0" style={{ width: '26px' }}>
                {TICKS.map((t) => (
                  <div
                    key={t.v}
                    className="absolute left-0 flex items-center"
                    style={{ top: `${t.top}%`, transform: 'translateY(-50%)' }}
                  >
                    <span className="block bg-gray-400" style={{ width: '4px', height: '1px' }} />
                    <span className="ml-1 text-[9px] tabular-nums font-semibold text-gray-100 leading-none">
                      {t.v}
                    </span>
                  </div>
                ))}
                {/* Floor marker at the base of the bar */}
                <div
                  className="absolute left-0 flex items-center"
                  style={{ top: '100%', transform: 'translateY(-50%)' }}
                >
                  <span className="block bg-gray-500" style={{ width: '4px', height: '1px' }} />
                  <span className="ml-1 text-[8px] tabular-nums text-gray-400 leading-none">{BASE_VAL}</span>
                </div>
              </div>

              {/* Rotated axis title */}
              <div className="flex items-center justify-center shrink-0" style={{ width: '14px' }}>
                <span
                  className="whitespace-nowrap text-[9px] text-gray-300 tracking-wide"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                >
                  Factor de reflectividad (dBZ)
                </span>
              </div>
            </div>

            {/* Floor note reconciling the 8 dBZ threshold */}
            <div className="mt-1 text-[8px] text-gray-500 leading-none">
              {'<'}{BASE_VAL} dBZ: transparente
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Mobile compact vertical panel ────────────────────── */
function MobileLegend({ barHeight }) {
  const minimized = useStore((s) => s.legendMinimized)
  const setLegendMinimized = useStore((s) => s.setLegendMinimized)
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className="sm:hidden fixed z-[999] text-white transition-all duration-200 left-2"
      style={{ bottom: `${barHeight + 8}px` }}
      role="region"
      aria-label="Leyenda de intensidad dBZ"
    >
      {/* Minimized: small floating button */}
      {minimized ? (
        <button
          onClick={() => setLegendMinimized(false)}
          className="flex items-center gap-1.5 bg-gray-950/90 backdrop-blur-sm rounded-lg
            shadow-xl border border-white/10 px-2 py-1.5
            active:bg-white/10 transition-colors touch-manipulation"
          aria-label="Mostrar leyenda"
        >
          <span
            className="w-4 h-4 rounded-sm shrink-0 border border-black/20"
            style={{ background: `linear-gradient(135deg, ${DBZ_LEGEND[0].color}, ${DBZ_LEGEND[6].color}, ${DBZ_LEGEND[12].color})` }}
            aria-hidden="true"
          />
          <span className="text-[10px] text-gray-400 font-semibold">dBZ</span>
          <i className="fas fa-chevron-up text-[7px] text-gray-500" />
        </button>
      ) : (
        <div className="bg-gray-950/90 backdrop-blur-sm rounded-lg shadow-xl border border-white/10
          overflow-hidden">

          {/* Header with minimize */}
          <div className="flex items-center justify-between gap-1 px-1.5 py-0.5">
            <span className="text-[9px] text-gray-400 font-semibold uppercase">
              dBZ
            </span>
            <button
              onClick={() => setLegendMinimized(true)}
              className="flex items-center justify-center w-4 h-4 rounded
                text-gray-500 active:bg-white/10 transition-colors touch-manipulation"
              aria-label="Minimizar leyenda"
            >
              <i className="fas fa-chevron-down text-[7px]" />
            </button>
          </div>

          {/* Escala continua (misma que escritorio, compacta) — tocar revela
              los nombres de categoría */}
          <div
            className="px-1.5 pb-1.5 cursor-pointer"
            onClick={() => setExpanded((v) => !v)}
            role="button"
            tabIndex={0}
            aria-expanded={expanded}
            aria-label="Escala de reflectividad; tocar para ver nombres de categoría"
          >
            <div className="flex items-stretch" style={{ height: `${MOBILE_BAR_H}px` }}>

              {/* Iconos de categoría (siempre) + nombres (al tocar), a la izquierda */}
              <div
                className="relative shrink-0 transition-all duration-200"
                style={{ width: expanded ? '60px' : '14px' }}
              >
                {CATEGORIES.map((c) => (
                  <div
                    key={c.l2}
                    className="absolute left-0 flex items-center gap-1"
                    style={{ top: `${c.top}%`, transform: 'translateY(-50%)' }}
                  >
                    <i className={`fas ${c.icon} text-[10px] text-gray-300 shrink-0`} />
                    {expanded && (
                      <span className="flex flex-col leading-tight text-[8px] font-medium text-gray-200">
                        <span className="whitespace-nowrap">{c.l1}</span>
                        <span className="whitespace-nowrap">{c.l2}</span>
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Barra de color clasificada */}
              <div
                className="shrink-0 overflow-hidden rounded-sm border border-black/40"
                style={{ width: '12px' }}
              >
                <div className="flex flex-col h-full">
                  {CELLS_TOP_DOWN.map((item) => (
                    <div key={item.range} style={{ flex: 1, backgroundColor: item.color }} />
                  ))}
                </div>
              </div>

              {/* Marcas numéricas (derecha de la barra) */}
              <div className="relative shrink-0" style={{ width: '18px' }}>
                {TICKS.map((t) => (
                  <div
                    key={t.v}
                    className="absolute left-0 flex items-center"
                    style={{ top: `${t.top}%`, transform: 'translateY(-50%)' }}
                  >
                    <span className="block bg-gray-400" style={{ width: '3px', height: '1px' }} />
                    <span className="ml-0.5 text-[8px] tabular-nums font-semibold text-gray-100 leading-none">
                      {t.v}
                    </span>
                  </div>
                ))}
                {/* Marca de piso en la base de la barra */}
                <div
                  className="absolute left-0 flex items-center"
                  style={{ top: '100%', transform: 'translateY(-50%)' }}
                >
                  <span className="block bg-gray-500" style={{ width: '3px', height: '1px' }} />
                  <span className="ml-0.5 text-[7px] tabular-nums text-gray-400 leading-none">{BASE_VAL}</span>
                </div>
              </div>
            </div>

            {/* Nota de piso — solo al expandir, para no ensanchar el panel colapsado */}
            {expanded && (
              <div className="mt-1 text-[7px] text-gray-500 leading-none">
                {'<'}{BASE_VAL} dBZ: transparente
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Main export ─────────────────────────────────────── */
export default function ColorLegend() {
  const [barHeight, setBarHeight] = useState(0)
  useEffect(() => {
    const handler = (e) => setBarHeight(e.detail.height || 0)
    window.addEventListener('animbar-resize', handler)
    return () => window.removeEventListener('animbar-resize', handler)
  }, [])

  return (
    <>
      <DesktopLegend barHeight={barHeight} />
      <MobileLegend barHeight={barHeight} />
    </>
  )
}
