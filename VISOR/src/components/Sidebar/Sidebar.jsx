import { useCallback, useEffect, useRef } from 'react'
import useStore from '../../store/useStore'
import { RADARS, BASE_LAYERS } from '../../config/radars'

/* ── Switch ──────────────────────────────────────────── */
function Switch({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={(e) => { e.stopPropagation(); onChange(!checked) }}
      className={`relative w-10 h-[22px] rounded-full shrink-0 transition-colors duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-400/60
        ${checked ? 'bg-blue-500' : 'bg-gray-600 hover:bg-gray-500'}`}
    >
      <span className={`absolute top-[3px] left-[3px] w-4 h-4 bg-white rounded-full shadow-sm
        transition-transform duration-200 ${checked ? 'translate-x-[18px]' : ''}`} />
    </button>
  )
}

/* ── Radar toggle row ────────────────────────────────── */
function RadarToggle({ radar, checked, onChange }) {
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors
      ${checked ? 'bg-white/5' : 'hover:bg-white/3'}`}>
      <span
        className="w-3 h-3 rounded-full shrink-0 border-2"
        style={{ backgroundColor: checked ? radar.colorHex : 'transparent', borderColor: radar.colorHex }}
      />
      <div className="flex-1 min-w-0">
        <span className="text-[13px] font-medium text-gray-100">{radar.name}</span>
        <span className="text-[11px] text-gray-500 ml-1.5">{radar.location}</span>
      </div>
      <Switch checked={checked} onChange={onChange} />
    </div>
  )
}

/* ── Toggle row ──────────────────────────────────────── */
function ToggleRow({ label, checked, onChange }) {
  return (
    <div className="flex items-center justify-between px-3 py-1.5">
      <span className="text-[13px] text-gray-300">{label}</span>
      <Switch checked={checked} onChange={onChange} />
    </div>
  )
}

/* ── Opacity slider ──────────────────────────────────── */
function OpacitySlider() {
  const opacity = useStore((s) => s.radarOpacity)
  const setRadarOpacity = useStore((s) => s.setRadarOpacity)

  return (
    <div className="px-3 py-1.5">
      <div className="flex items-center justify-between mb-1.5">
        <label htmlFor="opacity-slider" className="text-[13px] text-gray-300">
          Opacidad
        </label>
        <span className="text-[11px] font-semibold text-white bg-white/10 px-1.5 py-0.5 rounded tabular-nums">
          {opacity}%
        </span>
      </div>
      <div className="relative">
        <input
          id="opacity-slider"
          type="range"
          min={0}
          max={100}
          value={opacity}
          onChange={(e) => setRadarOpacity(parseInt(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none bg-gray-700 cursor-pointer
            [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:shadow-md
            [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:border-2
            [&::-webkit-slider-thumb]:border-blue-500
            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
            [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white
            [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-blue-500
            [&::-moz-range-thumb]:cursor-pointer"
          aria-label={`Opacidad: ${opacity}%`}
        />
        <div
          className="absolute top-0 left-0 h-1.5 bg-blue-500 rounded-full pointer-events-none"
          style={{ width: `${opacity}%` }}
        />
      </div>
    </div>
  )
}

/* ── Base layer selector ─────────────────────────────── */
function BaseLayerSelector() {
  const active = useStore((s) => s.activeBaseLayer)
  const setActive = useStore((s) => s.setActiveBaseLayer)

  return (
    <div className="px-3">
      <div className="inline-flex bg-white/5 rounded-lg p-0.5 border border-white/8 w-full">
        {Object.entries(BASE_LAYERS).map(([key, layer]) => (
          <button
            key={key}
            type="button"
            onClick={() => setActive(key)}
            aria-pressed={active === key}
            className={`flex-1 h-7 px-2 rounded-md text-[11px] font-semibold
              transition-all duration-150 touch-manipulation
              focus:outline-none focus:ring-1 focus:ring-blue-400/60
              ${active === key
                ? 'bg-blue-500 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/8'
              }`}
          >
            {layer.name}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── Radar info card ─────────────────────────────────── */
function RadarCard({ radar }) {
  const rows = [
    ['Cobertura', `${radar.coverageKm} km`],
    ['Resolución', radar.resolution],
    ['Actualización', radar.frequency],
    ['Coords', `${radar.lat.toFixed(4)}°, ${radar.lon.toFixed(4)}°`],
  ]

  return (
    <div className="bg-white/5 rounded-lg px-3 py-2 border border-white/5">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: radar.colorHex }} />
        <span className="font-semibold text-[12px] text-white">{radar.name}</span>
        <span className="text-[10px] text-gray-500">{radar.location}</span>
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <span className="text-gray-500">{label}</span>
            <span className="text-gray-300 tabular-nums">{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Section label ───────────────────────────────────── */
function SectionLabel({ children }) {
  return (
    <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold px-3">
      {children}
    </span>
  )
}

/* ── Main Sidebar ────────────────────────────────────── */
export default function Sidebar() {
  const isOpen = useStore((s) => s.sidebarOpen)
  const setSidebarOpen = useStore((s) => s.setSidebarOpen)
  const radarVisibility = useStore((s) => s.radarVisibility)
  const setRadarVisibility = useStore((s) => s.setRadarVisibility)
  const showMarkers = useStore((s) => s.showMarkers)
  const setShowMarkers = useStore((s) => s.setShowMarkers)
  const showCoverage = useStore((s) => s.showCoverage)
  const setShowCoverage = useStore((s) => s.setShowCoverage)
  const closeRef = useRef(null)

  const handleClose = useCallback(() => setSidebarOpen(false), [setSidebarOpen])

  useEffect(() => {
    if (!isOpen) return
    const h = (e) => { if (e.key === 'Escape') handleClose() }
    window.addEventListener('keydown', h)
    setTimeout(() => closeRef.current?.focus(), 100)
    return () => window.removeEventListener('keydown', h)
  }, [isOpen, handleClose])

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/50 z-[1001] transition-opacity duration-300
          ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        className={`fixed top-0 right-0 h-full w-[280px] max-w-[80vw]
          bg-gray-950 text-white z-[1002]
          transform transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]
          border-l border-white/10
          flex flex-col
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
        role="dialog"
        aria-modal="true"
        aria-label="Panel de configuración"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/8 shrink-0">
          <h2 className="text-sm font-bold flex items-center gap-2">
            <i className="fas fa-sliders-h text-blue-400 text-xs" />
            Configuración
          </h2>
          <button
            ref={closeRef}
            onClick={handleClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg
              hover:bg-white/10 active:bg-white/15 transition-colors touch-manipulation
              focus:outline-none focus:ring-2 focus:ring-blue-400/60 text-gray-400 hover:text-white"
            aria-label="Cerrar (Esc)"
          >
            <i className="fas fa-times text-sm" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain py-3 space-y-3">

          {/* Radares */}
          <div className="space-y-1">
            <SectionLabel>Radares</SectionLabel>
            <div className="space-y-0.5 px-1">
              {Object.entries(RADARS).map(([id, radar]) => (
                <RadarToggle
                  key={id}
                  radar={radar}
                  checked={radarVisibility[id]}
                  onChange={(v) => setRadarVisibility(id, v)}
                />
              ))}
            </div>
          </div>

          {/* Visualización */}
          <div className="space-y-1">
            <SectionLabel>Visualización</SectionLabel>
            <ToggleRow
              label="Marcadores"
              checked={showMarkers}
              onChange={setShowMarkers}
            />
            <ToggleRow
              label="Relleno cobertura"
              checked={showCoverage}
              onChange={setShowCoverage}
            />
            <OpacitySlider />
          </div>

          {/* Separator */}
          <div className="mx-3 border-t border-white/6" />

          {/* Mapa base */}
          <div className="space-y-1.5">
            <SectionLabel>Mapa base</SectionLabel>
            <BaseLayerSelector />
          </div>

          {/* Separator */}
          <div className="mx-3 border-t border-white/6" />

          {/* Info técnica */}
          <div className="space-y-1.5">
            <SectionLabel>Información técnica</SectionLabel>
            <div className="px-3 space-y-2">
              {Object.entries(RADARS).map(([id, radar]) => (
                <RadarCard key={id} radar={radar} />
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-3 py-2 border-t border-white/8 shrink-0">
          <p className="text-[10px] text-gray-600 text-center">
            © {new Date().getFullYear()} Universidad Técnica Particular de Loja
          </p>
        </div>
      </aside>
    </>
  )
}
