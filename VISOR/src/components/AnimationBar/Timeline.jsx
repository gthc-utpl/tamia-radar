import { useRef, useCallback, useMemo } from 'react'
import useStore from '../../store/useStore'
import { useAnimation } from '../../hooks/useAnimation'
import { formatTimeShort, formatDateShort, getLocalDate } from '../../utils/julianDate'
import { isImageCached } from '../../services/imageCache'

export default function Timeline() {
  const frames = useStore((s) => s.frames)
  const currentFrameIndex = useStore((s) => s.currentFrameIndex)
  const radarFrames = useStore((s) => s.radarFrames)
  const { seekTo, totalFrames } = useAnimation()
  const trackRef = useRef(null)
  const isDragging = useRef(false)

  const progress = totalFrames > 1 ? (currentFrameIndex / (totalFrames - 1)) * 100 : 0

  const handleInteraction = useCallback(
    (clientX) => {
      if (!trackRef.current || totalFrames === 0) return
      const rect = trackRef.current.getBoundingClientRect()
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width))
      seekTo(Math.round((x / rect.width) * (totalFrames - 1)))
    },
    [totalFrames, seekTo]
  )

  const startDrag = useCallback(
    (startX) => {
      isDragging.current = true
      handleInteraction(startX)
    },
    [handleInteraction]
  )

  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    startDrag(e.clientX)
    const move = (ev) => handleInteraction(ev.clientX)
    const up = () => {
      isDragging.current = false
      document.removeEventListener('mousemove', move)
      document.removeEventListener('mouseup', up)
    }
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', up)
  }, [startDrag, handleInteraction])

  const handleTouchStart = useCallback((e) => {
    startDrag(e.touches[0].clientX)
    const move = (ev) => { ev.preventDefault(); handleInteraction(ev.touches[0].clientX) }
    const end = () => {
      isDragging.current = false
      document.removeEventListener('touchmove', move)
      document.removeEventListener('touchend', end)
    }
    document.addEventListener('touchmove', move, { passive: false })
    document.addEventListener('touchend', end)
  }, [startDrag, handleInteraction])

  const ticks = useMemo(() => {
    if (totalFrames <= 1) return []
    const max = Math.min(6, totalFrames)
    const step = Math.max(1, Math.floor((totalFrames - 1) / (max - 1)))
    const r = []
    for (let i = 0; i < totalFrames; i += step) r.push(i)
    if (r[r.length - 1] !== totalFrames - 1) r.push(totalFrames - 1)
    return r
  }, [totalFrames])

  // Detect if timeline spans multiple days
  const { spansMultipleDays, dayBoundaries, dateLabel } = useMemo(() => {
    if (totalFrames === 0) return { spansMultipleDays: false, dayBoundaries: [], dateLabel: '' }

    const firstDate = getLocalDate(frames[0])
    const lastDate = getLocalDate(frames[totalFrames - 1])
    const spans = firstDate !== lastDate

    const boundaries = []
    if (spans) {
      for (let i = 1; i < totalFrames; i++) {
        const prevDay = getLocalDate(frames[i - 1])
        const currDay = getLocalDate(frames[i])
        if (prevDay !== currDay) {
          boundaries.push({
            index: i,
            pct: (i / Math.max(totalFrames - 1, 1)) * 100,
            date: formatDateShort(frames[i]),
          })
        }
      }
    }

    const label = spans
      ? `${formatDateShort(frames[0])} — ${formatDateShort(frames[totalFrames - 1])}`
      : formatDateShort(frames[0])

    return { spansMultipleDays: spans, dayBoundaries: boundaries, dateLabel: label }
  }, [totalFrames, frames])

  const bufferSegments = useMemo(() => {
    if (totalFrames === 0) return []
    const cachedUrls = new Set()
    Object.values(radarFrames).flat().forEach((r) => {
      if (isImageCached(r.url)) cachedUrls.add(r.url)
    })
    return Array.from({ length: totalFrames }, (_, i) => {
      const ts = frames[i]
      if (!ts) return false
      return Object.values(radarFrames).some((recs) =>
        recs.some((r) => Math.abs(r.timestamp - ts) < 600000 && cachedUrls.has(r.url))
      )
    })
  }, [totalFrames, frames, radarFrames])

  if (totalFrames === 0) return null

  const denom = Math.max(totalFrames - 1, 1)

  return (
    <div className="w-full px-3 select-none">
      {/* Date label + day boundary labels above track */}
      <div className="relative pt-1 pb-0.5">
        <div className="flex items-center justify-center">
          <span className="text-[10px] text-gray-400 font-medium tracking-wide">
            <i className="fas fa-calendar-day text-gray-500 mr-1 text-[9px]" />
            {dateLabel}
          </span>
        </div>
        {dayBoundaries.map((b, idx) => (
          <span key={`dbl${idx}`}
            className="absolute bottom-0 -translate-x-1/2 text-amber-400/90 text-[9px] font-semibold whitespace-nowrap"
            style={{ left: `${b.pct}%` }}
          >
            {b.date}
          </span>
        ))}
      </div>

      {/* Track — 32px touch target */}
      <div
        ref={trackRef}
        className="relative w-full h-8 flex items-center cursor-pointer group"
        role="slider"
        aria-label="Línea de tiempo"
        aria-valuemin={0}
        aria-valuemax={totalFrames - 1}
        aria-valuenow={currentFrameIndex}
        aria-valuetext={frames[currentFrameIndex] ? formatTimeShort(frames[currentFrameIndex]) : ''}
        tabIndex={0}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
        onKeyDown={(e) => {
          switch (e.key) {
            case 'ArrowRight': e.preventDefault(); seekTo(currentFrameIndex + 1); break
            case 'ArrowLeft': e.preventDefault(); seekTo(currentFrameIndex - 1); break
            case 'Home': e.preventDefault(); seekTo(0); break
            case 'End': e.preventDefault(); seekTo(totalFrames - 1); break
          }
        }}
      >
        {/* Track bg */}
        <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-1 bg-white/10 rounded-full overflow-hidden">
          {bufferSegments.map((ok, i) => ok ? (
            <div key={i} className="absolute top-0 h-full bg-white/8 rounded-full"
              style={{ left: `${(i / denom) * 100}%`, width: `${Math.max(100 / denom, 0.5)}%` }}
            />
          ) : null)}
          <div
            className="h-full bg-blue-500 rounded-full transition-[width] duration-75"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Day boundary markers */}
        {dayBoundaries.map((b, idx) => (
          <div key={`db${idx}`}
            className="absolute top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ left: `${b.pct}%` }}
          >
            <div className="w-px h-5 bg-amber-400/50" />
          </div>
        ))}

        {/* Tick marks */}
        {ticks.map((i) => (
          <div key={`t${i}`}
            className="absolute top-1/2 -translate-y-1/2 w-px h-2 bg-white/20 rounded-full pointer-events-none"
            style={{ left: `${(i / denom) * 100}%` }}
          />
        ))}

        {/* Thumb */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 pointer-events-none transition-[left] duration-75"
          style={{ left: `${progress}%` }}
        >
          <div className="w-3.5 h-3.5 rounded-full bg-white shadow-md shadow-black/40 border-2 border-blue-500
            group-hover:scale-110 group-active:scale-125 transition-transform" />
        </div>
      </div>

      {/* Tick labels */}
      <div className="relative w-full h-3.5 text-[9px] text-gray-500 tabular-nums leading-none">
        {ticks.map((i, idx) => {
          const pct = (i / denom) * 100
          const isFirst = idx === 0
          const isLast = idx === ticks.length - 1

          let label = frames[i] ? formatTimeShort(frames[i]) : ''
          if (spansMultipleDays && (isFirst || isLast)) {
            label = `${formatDateShort(frames[i])} ${label}`
          }

          return (
            <span key={i}
              className={`absolute whitespace-nowrap
                ${isFirst ? 'left-0' : isLast ? 'right-0' : '-translate-x-1/2'}`}
              style={!isFirst && !isLast ? { left: `${pct}%` } : undefined}
            >
              {label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
