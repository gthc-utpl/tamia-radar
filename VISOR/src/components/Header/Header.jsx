import { useState, useEffect } from 'react'
import useStore from '../../store/useStore'
import { useCurrentFrame } from '../../hooks/useCurrentFrame'
import { formatDateTimeFull } from '../../utils/julianDate'

function timeAgo(timestamp) {
  const diff = Date.now() - timestamp
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'ahora'
  if (mins < 60) return `hace ${mins} min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs}h ${mins % 60}m`
  return `hace ${Math.floor(hrs / 24)}d`
}

function getStatusColor(timestamp) {
  const mins = (Date.now() - timestamp) / 60000
  if (mins < 10) return { dot: 'bg-green-400', text: 'text-green-300' }
  if (mins < 30) return { dot: 'bg-amber-400', text: 'text-amber-300' }
  return { dot: 'bg-red-400', text: 'text-red-300' }
}

export default function Header() {
  const latestRecords = useStore((s) => s.latestRecords)
  const animationActive = useStore((s) => s.animationActive)
  const frameData = useCurrentFrame()
  const [, setTick] = useState(0)

  // Re-render every 30s to keep "hace X min" updated
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 30000)
    return () => clearInterval(id)
  }, [])

  // During animation, show frame timestamp (no "hace" needed)
  if (animationActive && frameData?.timestamp) {
    const formatted = formatDateTimeFull(frameData.timestamp)
    return (
      <header className="bg-[#1e478e] text-white shadow-lg z-[1001] relative">
        <div className="flex items-center justify-between px-3 py-2 gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <img src="https://utpl.edu.ec/recursos/img/utpl1.png" alt="UTPL" className="h-8 w-auto hidden sm:block" />
            <div className="min-w-0">
              <h1 className="text-sm sm:text-base font-semibold truncate">Sistema Multi-Radar Meteorológico</h1>
              <p className="text-[10px] sm:text-xs text-blue-200 truncate">Observatorio de Clima - UTPL</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 bg-white/10 rounded-lg px-2.5 py-1.5">
            <i className="fas fa-film text-[10px] text-blue-300" />
            <div className="flex flex-col items-end leading-tight">
              <span className="text-xs font-semibold text-white">{formatted.time} LT</span>
              <span className="text-[10px] text-blue-200">{formatted.date}</span>
            </div>
          </div>
        </div>
      </header>
    )
  }

  // Normal mode — show latest data with "hace X min"
  const records = Object.values(latestRecords).filter(Boolean)
  let displayTime = null
  if (records.length > 0) {
    const newest = records.reduce((a, b) => a.timestamp > b.timestamp ? a : b)
    displayTime = newest.timestamp
  }

  const formatted = displayTime ? formatDateTimeFull(displayTime) : null
  const status = displayTime ? getStatusColor(displayTime) : null
  const ago = displayTime ? timeAgo(displayTime) : null

  return (
    <header className="bg-[#1e478e] text-white shadow-lg z-[1001] relative">
      <div className="flex items-center justify-between px-3 py-2 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <img src="https://utpl.edu.ec/recursos/img/utpl1.png" alt="UTPL" className="h-8 w-auto hidden sm:block" />
          <div className="min-w-0">
            <h1 className="text-sm sm:text-base font-semibold truncate">Sistema Multi-Radar Meteorológico</h1>
            <p className="text-[10px] sm:text-xs text-blue-200 truncate">Observatorio de Clima - UTPL</p>
          </div>
        </div>

        {formatted ? (
          <div className="flex items-center gap-2 shrink-0 bg-white/10 rounded-lg px-2.5 py-1.5">
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${status.dot} ${status.dot === 'bg-green-400' ? 'animate-pulse' : ''}`}
              aria-hidden="true"
            />
            <div className="flex flex-col items-end leading-tight">
              <span className="text-xs font-semibold text-white">{formatted.time} LT</span>
              <span className={`text-[10px] ${status.text}`}>{ago}</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 shrink-0 bg-white/10 rounded-lg px-2.5 py-1.5">
            <span className="w-2 h-2 rounded-full bg-gray-500 shrink-0" aria-hidden="true" />
            <span className="text-[11px] text-gray-400">Sin datos</span>
          </div>
        )}
      </div>
    </header>
  )
}
