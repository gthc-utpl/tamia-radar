import { useState, useEffect, useRef } from 'react'
import useStore from '../../store/useStore'
import { getFreshness } from '../../utils/freshness'
import { RADARS } from '../../config/radars'

export default function MaintenanceBanner() {
  const latestRecords = useStore((s) => s.latestRecords)
  const animationActive = useStore((s) => s.animationActive)
  const [dismissed, setDismissed] = useState(false)
  const prevBothOffline = useRef(false)

  const bothOffline = Object.keys(RADARS).every((id) => {
    const f = getFreshness(latestRecords[id]?.timestamp)
    return f === 'no-data' || f === 'offline'
  })

  // Reset dismissed when radars come back, so banner shows again if they go offline again
  useEffect(() => {
    if (!bothOffline && prevBothOffline.current) {
      setDismissed(false)
    }
    prevBothOffline.current = bothOffline
  }, [bothOffline])

  if (!bothOffline || dismissed || animationActive) return null

  return (
    <div
      className="absolute inset-0 z-[1002] flex items-center justify-center pointer-events-none"
      aria-live="assertive"
    >
      <div className="pointer-events-auto mx-4 w-full max-w-md rounded-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between bg-[#1e478e] px-4 py-2.5">
          <div className="flex items-center gap-2">
            <i className="fas fa-exclamation-triangle text-amber-300 text-sm" />
            <span className="text-white font-semibold text-sm">
              Mensaje de clima.utpl.edu.ec
            </span>
          </div>
          <button
            onClick={() => setDismissed(true)}
            aria-label="Cerrar aviso"
            className="text-white/70 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-white/50 rounded"
          >
            <i className="fas fa-times text-sm" />
          </button>
        </div>

        {/* Body */}
        <div className="bg-white px-5 py-4">
          <p className="text-gray-700 text-sm leading-relaxed text-justify">
            Los radares meteorológicos <strong>GUAXX (Celica)</strong> y{' '}
            <strong>LOXX (Loja)</strong> no están transmitiendo información en
            este momento. Es posible que los equipos se encuentren en proceso de
            mantenimiento o presenten una interrupción temporal en la señal. El
            visor actualizará los datos automáticamente cuando se restablezca la
            transmisión. Agradecemos tu interés en el monitoreo meteorológico de
            la UTPL.
          </p>
        </div>
      </div>
    </div>
  )
}
