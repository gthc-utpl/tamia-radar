import { useState, useEffect } from 'react'
import useStore from '../../store/useStore'
import { useCurrentFrame } from '../../hooks/useCurrentFrame'
import { formatDateTimeFull } from '../../utils/julianDate'
import { getFreshness, formatAge } from '../../utils/freshness'
import { RADARS } from '../../config/radars'

// Indicador discreto de estado del WebSocket en vivo. Se oculta si el WS
// está deshabilitado (VITE_ENABLE_WS != 'true') o aún sin inicializar.
function LiveIndicator() {
  const wsStatus = useStore((s) => s.wsStatus)

  // Ícono (no un punto) para no confundirse con el punto de frescura del radar.
  const cfg = {
    connected: { icon: 'fa-wifi', text: 'En vivo', cls: 'text-green-300' },
    connecting: { icon: 'fa-circle-notch fa-spin', text: 'Conectando…', cls: 'text-amber-300' },
    disconnected: { icon: 'fa-circle-notch fa-spin', text: 'Reconectando…', cls: 'text-gray-300' },
    error: { icon: 'fa-exclamation-triangle', text: 'Sin conexión', cls: 'text-red-300' },
  }[wsStatus]

  if (!cfg) return null // 'idle' | 'disabled' | desconocido → no mostrar nada

  return (
    <div className="flex items-center gap-1.5 shrink-0" title={`WebSocket: ${wsStatus}`}>
      <i className={`fas ${cfg.icon} text-[10px] ${cfg.cls}`} aria-hidden="true" />
      <span className={`text-[10px] font-semibold ${cfg.cls}`}>{cfg.text}</span>
    </div>
  )
}

function RadarStatusBadge({ radarId, record }) {
  const freshness = getFreshness(record?.timestamp)
  const age = record ? formatAge(record.timestamp) : null
  const formatted = record ? formatDateTimeFull(record.timestamp) : null
  const isRecent = freshness === 'fresh' || freshness === 'stale'

  const dotClass = {
    fresh: 'bg-green-400 animate-pulse',
    stale: 'bg-amber-400',
    offline: 'bg-red-400',
    'no-data': 'bg-gray-500',
  }[freshness]

  const ageClass = {
    fresh: 'text-green-300',
    stale: 'text-amber-300',
    offline: 'text-red-300',
    'no-data': 'text-gray-400',
  }[freshness]

  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotClass}`} aria-hidden="true" />
      <span className="text-[10px] font-bold text-white/60 uppercase shrink-0">{radarId}</span>
      {isRecent && formatted && (
        <span className="text-[10px] font-semibold text-white">{formatted.time} LT</span>
      )}
      <span className={`text-[10px] ${ageClass}`}>
        {age ?? 'sin datos'}
      </span>
    </div>
  )
}

export default function Header() {
  const latestRecords = useStore((s) => s.latestRecords)
  const animationActive = useStore((s) => s.animationActive)
  const frameData = useCurrentFrame()
  const [, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 30000)
    return () => clearInterval(id)
  }, [])

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

  const hasAnyRecord = Object.values(latestRecords).some(Boolean)

  return (
    <header className="bg-[#1e478e] text-white shadow-lg z-[1001] relative">
      <div className="flex items-center justify-between px-3 py-2 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <img src="https://utpl.edu.ec/recursos/img/utpl1.png" alt="UTPL" className="h-8 w-auto hidden sm:block" />
          <div className="min-w-0">
            <h1 className="text-sm sm:text-base font-semibold truncate">Sistema Multi-Radar Meteorológico</h1>
            <div className="flex items-center gap-2">
              <p className="text-[10px] sm:text-xs text-blue-200 truncate">Observatorio de Clima - UTPL</p>
              <LiveIndicator />
            </div>
          </div>
        </div>

        {hasAnyRecord ? (
          <div className="flex flex-col gap-0.5 shrink-0 bg-white/10 rounded-lg px-2.5 py-1.5">
            {Object.keys(RADARS).map((id) => (
              <RadarStatusBadge key={id} radarId={id} record={latestRecords[id]} />
            ))}
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
