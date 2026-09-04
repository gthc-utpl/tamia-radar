import { useCallback, useEffect, useRef, useState } from 'react'
import useStore from '../../store/useStore'
import { useAnimation } from '../../hooks/useAnimation'
import { useCurrentFrame } from '../../hooks/useCurrentFrame'
import { useRadarData } from '../../hooks/useRadarData'
import { ANIMATION_CONFIG } from '../../config/radars'
import { formatTimestamp, toDatetimeLocalString } from '../../utils/julianDate'
import Timeline from './Timeline'

/* ── Icon button ─────────────────────────────────────── */
function Btn({ onClick, icon, label, disabled = false, primary = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`flex items-center justify-center shrink-0 rounded-full
        transition-all duration-100 touch-manipulation
        disabled:opacity-30 disabled:cursor-not-allowed
        focus:outline-none focus:ring-2 focus:ring-blue-400/60
        ${primary
          ? 'w-9 h-9 bg-blue-500 hover:bg-blue-600 active:bg-blue-700 text-white shadow-md shadow-blue-500/25'
          : 'w-8 h-8 hover:bg-white/10 active:bg-white/15 text-gray-300'
        }`}
    >
      <i className={`fas ${icon} ${primary ? 'text-sm' : 'text-xs'}`} />
    </button>
  )
}

/* ── Inline pill selector ────────────────────────────── */
function Pills({ options, value, onChange, disabled = false }) {
  return (
    <div className="inline-flex bg-white/5 rounded-md p-0.5 border border-white/8">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          disabled={disabled}
          aria-pressed={value === opt.value}
          className={`min-w-[28px] h-6 px-1.5 rounded text-[11px] font-semibold
            transition-all duration-100 touch-manipulation
            disabled:opacity-40
            focus:outline-none focus:ring-1 focus:ring-blue-400/60
            ${value === opt.value
              ? 'bg-blue-500 text-white shadow-sm'
              : 'text-gray-500 hover:text-gray-300 hover:bg-white/8'
            }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

/* ── Main AnimationBar ────────────────────────────────── */
export default function AnimationBar() {
  const animationActive = useStore((s) => s.animationActive)
  const currentFrameIndex = useStore((s) => s.currentFrameIndex)
  const isLoading = useStore((s) => s.isLoading)
  const preloadProgress = useStore((s) => s.preloadProgress)
  const period = useStore((s) => s.period)
  const setPeriod = useStore((s) => s.setPeriod)
  const speed = useStore((s) => s.speed)
  const setSpeed = useStore((s) => s.setSpeed)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  const customDate = useStore((s) => s.customDate)
  const setCustomDate = useStore((s) => s.setCustomDate)
  const frameData = useCurrentFrame()

  const [dateStatus, setDateStatus] = useState(null)
  const [mobileExpanded, setMobileExpanded] = useState(false)
  const barRef = useRef(null)
  const endDateRef = useRef(null)
  const hasAutoPlayed = useRef(false)

  const {
    nextFrame, prevFrame, goToFirst, goToLast, togglePlay,
    totalFrames, isPlaying,
  } = useAnimation()
  const { loadAnimationData, refreshAnimationFrames } = useRadarData()

  const loadData = useCallback((endDate) => {
    setDateStatus(null)
    const date = endDate || endDateRef.current || new Date()
    endDateRef.current = date
    loadAnimationData(date, period)
  }, [loadAnimationData, period])

  useEffect(() => {
    if (animationActive) loadData()
    else hasAutoPlayed.current = false
  }, [animationActive, period])

  // Auto-play on first load after activation
  useEffect(() => {
    if (animationActive && !isLoading && totalFrames > 0 && !hasAutoPlayed.current) {
      hasAutoPlayed.current = true
      setIsPlaying(true)
    }
  }, [animationActive, isLoading, totalFrames, setIsPlaying])

  // Auto-refresh frames during live-mode animation
  const isLiveMode = !customDate
  useEffect(() => {
    if (!animationActive || !isLiveMode) return

    const tick = () => {
      if (!document.hidden) {
        refreshAnimationFrames(period)
      }
    }

    const id = setInterval(tick, ANIMATION_CONFIG.autoRefreshInterval)
    return () => clearInterval(id)
  }, [animationActive, isLiveMode, period, refreshAnimationFrames])

  const handleGoLive = useCallback(() => {
    setCustomDate(null)
    setDateStatus(null)
    endDateRef.current = null
    loadData(new Date())
  }, [loadData])

  const handleApplyCustomDate = useCallback(() => {
    if (!customDate || !customDate.trim()) {
      setDateStatus({ type: 'error', msg: 'Seleccione una fecha y hora.' })
      return
    }
    const d = new Date(customDate)
    if (d > new Date()) {
      setDateStatus({ type: 'error', msg: 'La fecha no puede ser futura.' })
      return
    }
    if ((new Date() - d) / 864e5 > 30) {
      setDateStatus({ type: 'warning', msg: 'Datos antiguos (>30 días) podrían no estar disponibles.' })
    } else {
      setDateStatus(null)
    }
    loadData(d)
  }, [loadData, customDate])

  // Keyboard shortcuts
  useEffect(() => {
    if (!animationActive) return
    const h = (e) => {
      if (e.key === 'Enter' && e.target.id === 'custom-date-input') {
        e.preventDefault(); handleApplyCustomDate(); return
      }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      switch (e.key) {
        case ' ': e.preventDefault(); togglePlay(); break
        case 'ArrowRight':
          if (!e.target.closest('[role="slider"]')) { e.preventDefault(); nextFrame() }
          break
        case 'ArrowLeft':
          if (!e.target.closest('[role="slider"]')) { e.preventDefault(); prevFrame() }
          break
        case 'Home': e.preventDefault(); goToFirst(); break
        case 'End': e.preventDefault(); goToLast(); break
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [animationActive, togglePlay, nextFrame, prevFrame, goToFirst, goToLast, handleApplyCustomDate])

  // Notify FABs/Legend of height changes
  useEffect(() => {
    if (!animationActive) {
      window.dispatchEvent(new CustomEvent('animbar-resize', { detail: { height: 0 } }))
      return
    }
    if (!barRef.current) return
    const ro = new ResizeObserver(() => {
      window.dispatchEvent(new CustomEvent('animbar-resize', {
        detail: { height: barRef.current?.offsetHeight || 0 }
      }))
    })
    ro.observe(barRef.current)
    return () => ro.disconnect()
  }, [animationActive])

  if (!animationActive) return null

  const currentTime = frameData?.timestamp
    ? formatTimestamp(frameData.timestamp)
    : '--:-- LT'

  const noData = totalFrames === 0
  const ctrl = isLoading || noData

  return (
    <div
      ref={barRef}
      className="fixed bottom-0 left-0 right-0 z-[1000]
        bg-gray-950/95 backdrop-blur-md text-white
        border-t border-white/10 shadow-[0_-2px_20px_rgba(0,0,0,0.5)]
        safe-area-bottom"
      role="region"
      aria-label="Controles de animación"
    >
      {/* Preload progress */}
      {preloadProgress && (
        <div className="h-0.5 bg-gray-800">
          <div
            className="h-full bg-blue-400 transition-[width] duration-200"
            style={{ width: `${(preloadProgress.loaded / preloadProgress.total) * 100}%` }}
          />
        </div>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-1 text-[11px] text-blue-300">
          <i className="fas fa-circle-notch fa-spin text-[10px]" />
          {preloadProgress
            ? `Precargando ${preloadProgress.loaded}/${preloadProgress.total}`
            : 'Cargando…'}
        </div>
      )}

      {/* Timeline */}
      <Timeline />

      {/* ════════ DESKTOP ════════ */}
      <div className="hidden sm:flex items-center gap-2 px-3 pb-3 pt-2">
        {/* Zone 1 — Status */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="font-semibold text-sm tabular-nums tracking-wide">{currentTime}</span>
          {!noData && !isLoading && (
            <span className="text-[10px] text-gray-500 tabular-nums">
              {currentFrameIndex + 1}/{totalFrames}
            </span>
          )}
        </div>

        <div className="w-px h-6 bg-white/8" />

        {/* Zone 2 — Playback + Speed */}
        <div className="flex-1 flex items-center justify-center gap-2">
          <div className="flex items-center gap-0.5">
            <Btn onClick={goToFirst} icon="fa-backward-fast" label="Primer frame" disabled={ctrl} />
            <Btn onClick={prevFrame} icon="fa-backward-step" label="Anterior" disabled={ctrl} />
            <Btn onClick={togglePlay} icon={isPlaying ? 'fa-pause' : 'fa-play'} label={isPlaying ? 'Pausar' : 'Reproducir'} disabled={ctrl} primary />
            <Btn onClick={nextFrame} icon="fa-forward-step" label="Siguiente" disabled={ctrl} />
            <Btn onClick={goToLast} icon="fa-forward-fast" label="Último frame" disabled={ctrl} />
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[10px] text-gray-500 uppercase font-semibold">Velocidad</span>
            <Pills options={ANIMATION_CONFIG.speeds} value={speed} onChange={setSpeed} />
          </div>
        </div>

        <div className="w-px h-6 bg-white/8" />

        {/* Zone 3 — Data config */}
        <div className="flex items-center gap-1.5 shrink-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-500 uppercase font-semibold">Intervalo</span>
            <Pills options={ANIMATION_CONFIG.periods} value={period} onChange={setPeriod} disabled={isLoading} />
          </div>
          <div className="w-px h-5 bg-white/6" />
          <button
            onClick={isLiveMode ? undefined : handleGoLive}
            disabled={isLoading}
            title={isLiveMode ? 'Modo en vivo — auto-actualización activa' : 'Volver a tiempo real'}
            className={`h-7 px-2 rounded-md text-[11px] font-semibold flex items-center gap-1.5
              transition-colors disabled:opacity-50 touch-manipulation shrink-0
              focus:outline-none focus:ring-2 focus:ring-blue-400/60
              ${isLiveMode
                ? 'bg-green-500/15 text-green-400 border border-green-500/30 cursor-default'
                : 'bg-gray-800 text-gray-400 border border-white/10 hover:text-white hover:bg-gray-700 cursor-pointer'
              }`}
          >
            <span className={`inline-block w-1.5 h-1.5 rounded-full
              ${isLiveMode ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
            En vivo
          </button>
          <span className="text-[10px] text-gray-500 uppercase font-semibold">Fecha</span>
          <input
            id="custom-date-input"
            type="datetime-local"
            value={customDate || toDatetimeLocalString(new Date())}
            onChange={(e) => { setCustomDate(e.target.value); setDateStatus(null) }}
            max={toDatetimeLocalString(new Date())}
            title={`Fecha final — se cargarán ${period}h previas`}
            className="bg-gray-900/60 text-white text-xs px-2 h-7 w-44
              rounded-md border border-white/12
              focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30
              [color-scheme:dark]"
          />
          <button
            onClick={handleApplyCustomDate}
            disabled={isLoading}
            title={`Cargar ${period}h previas a la fecha seleccionada`}
            className="h-7 px-2.5 bg-blue-500 hover:bg-blue-600 active:bg-blue-700
              text-white text-[11px] font-semibold rounded-md transition-colors
              disabled:opacity-50 touch-manipulation
              focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Cargar
          </button>
        </div>

        {dateStatus && (
          <span className={`text-[11px] flex items-center gap-1 shrink-0
            ${dateStatus.type === 'error' ? 'text-red-400' : 'text-amber-400'}
          `}>
            <i className={`fas text-[9px]
              ${dateStatus.type === 'error' ? 'fa-exclamation-circle' : 'fa-exclamation-triangle'}
            `} />
            {dateStatus.msg}
          </span>
        )}
      </div>

      {/* ════════ MOBILE ════════ */}
      <div className="sm:hidden px-3 pb-2 pt-0.5">
        {/* Always visible: Time + Playback */}
        <div className="flex items-center justify-between">
          {/* Time */}
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-sm tabular-nums">{currentTime}</span>
            {!noData && !isLoading && (
              <span className="text-[10px] text-gray-500 tabular-nums">
                {currentFrameIndex + 1}/{totalFrames}
              </span>
            )}
          </div>

          {/* Playback */}
          <div className="flex items-center gap-0.5">
            <Btn onClick={goToFirst} icon="fa-backward-fast" label="Primer frame" disabled={ctrl} />
            <Btn onClick={prevFrame} icon="fa-backward-step" label="Anterior" disabled={ctrl} />
            <Btn onClick={togglePlay} icon={isPlaying ? 'fa-pause' : 'fa-play'} label={isPlaying ? 'Pausar' : 'Reproducir'} disabled={ctrl} primary />
            <Btn onClick={nextFrame} icon="fa-forward-step" label="Siguiente" disabled={ctrl} />
            <Btn onClick={goToLast} icon="fa-forward-fast" label="Último frame" disabled={ctrl} />
          </div>
        </div>

        {/* Accordion toggle */}
        <button
          onClick={() => setMobileExpanded((v) => !v)}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 mt-1
            text-[10px] text-gray-500 hover:text-gray-300 transition-colors touch-manipulation"
        >
          <span className="uppercase font-semibold tracking-wider">
            {mobileExpanded ? 'Menos opciones' : 'Más opciones'}
          </span>
          <i className={`fas fa-chevron-down text-[8px] transition-transform duration-200
            ${mobileExpanded ? 'rotate-180' : ''}`} />
        </button>

        {/* Expandable options */}
        {mobileExpanded && (
          <div className="space-y-2 pt-0.5 pb-0.5 animate-[slideDown_0.15s_ease-out]">
            {/* Period + Speed + Refresh */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-gray-500 uppercase font-semibold">Intervalo</span>
                  <Pills options={ANIMATION_CONFIG.periods} value={period} onChange={setPeriod} disabled={isLoading} />
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-gray-500 uppercase font-semibold">Velocidad</span>
                  <Pills options={ANIMATION_CONFIG.speeds} value={speed} onChange={setSpeed} />
                </div>
              </div>
            </div>

            {/* Date input + Live button */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={isLiveMode ? undefined : handleGoLive}
                disabled={isLoading}
                title={isLiveMode ? 'Modo en vivo' : 'Volver a tiempo real'}
                className={`h-7 px-2 rounded-md text-[10px] font-semibold flex items-center gap-1 shrink-0
                  transition-colors disabled:opacity-50 touch-manipulation
                  ${isLiveMode
                    ? 'bg-green-500/15 text-green-400 border border-green-500/30 cursor-default'
                    : 'bg-gray-800 text-gray-400 border border-white/10 hover:text-white hover:bg-gray-700 cursor-pointer'
                  }`}
              >
                <span className={`inline-block w-1.5 h-1.5 rounded-full
                  ${isLiveMode ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
                En vivo
              </button>
              <span className="text-[9px] text-gray-500 uppercase font-semibold shrink-0">Fecha</span>
              <input
                type="datetime-local"
                value={customDate || toDatetimeLocalString(new Date())}
                onChange={(e) => { setCustomDate(e.target.value); setDateStatus(null) }}
                max={toDatetimeLocalString(new Date())}
                className="flex-1 min-w-0 bg-gray-900/60 text-white text-xs px-2 h-7
                  rounded-md border border-white/12
                  focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30
                  [color-scheme:dark]"
              />
              <button
                onClick={handleApplyCustomDate}
                disabled={isLoading}
                className="h-7 px-2.5 bg-blue-500 hover:bg-blue-600 active:bg-blue-700
                  text-white text-[11px] font-semibold rounded-md transition-colors shrink-0
                  disabled:opacity-50 touch-manipulation"
              >
                Cargar
              </button>
            </div>
            {dateStatus && (
              <div className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md
                ${dateStatus.type === 'error' ? 'bg-red-500/10 text-red-300' : 'bg-amber-500/10 text-amber-300'}
              `}>
                <i className={`fas text-[9px] shrink-0
                  ${dateStatus.type === 'error' ? 'fa-exclamation-circle' : 'fa-exclamation-triangle'}
                `} />
                <span>{dateStatus.msg}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
