import { useEffect, useRef } from 'react'
import useStore from '../store/useStore'
import { createRadarSocket } from '../services/websocketClient'
import { API_BASE } from '../services/radarService'

// Interruptor por entorno: el WebSocket solo se activa si VITE_ENABLE_WS === 'true'.
// Permite publicar el build con el socket apagado y encenderlo/apagarlo sin re-desplegar
// código, dejando el polling de 3 min de App.jsx como respaldo real.
const WS_ENABLED = import.meta.env.VITE_ENABLE_WS === 'true'

/**
 * Conecta al canal /ws/radar/updates de la API y actualiza latestRecords
 * directamente cuando llega un frame nuevo (sin refetch). El polling de
 * App.jsx (AUTO_REFRESH_MS) no se toca: sigue siendo el respaldo real para
 * clientes sin conexión WebSocket activa.
 */
export function useWebSocketUpdates() {
  const setLatestRecord = useStore((s) => s.setLatestRecord)
  const setWsStatus = useStore((s) => s.setWsStatus)
  const animationActive = useStore((s) => s.animationActive)
  const animationActiveRef = useRef(animationActive)

  useEffect(() => {
    animationActiveRef.current = animationActive
  }, [animationActive])

  useEffect(() => {
    if (!WS_ENABLED) {
      setWsStatus?.('disabled')
      return
    }

    const socket = createRadarSocket({
      onStatusChange: setWsStatus,
      onFrame: (msg) => {
        // Durante la animación el timeline se maneja aparte
        // (refreshAnimationFrames); no se toca el estado "en vivo" aquí.
        if (animationActiveRef.current) return
        setLatestRecord(msg.radar_id, {
          radarId: msg.radar_id,
          filename: msg.filename,
          url: `${API_BASE}${msg.url}`,
          bounds: msg.bounds,
          timestamp: new Date(msg.timestamp.replace(' ', 'T')),
        })
      },
    })
    socket.start()
    return () => socket.stop()
  }, [setLatestRecord, setWsStatus])
}
