// websocketClient.js — cliente WebSocket para /ws/radar/updates con
// reconexión automática. Complementa (no reemplaza) el polling de App.jsx:
// si el socket se cae o el proxy no deja pasar el upgrade, el polling de
// 3 min sigue funcionando exactamente igual que hoy.
import { API_BASE } from './radarService'

const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/radar/updates'
const BASE_BACKOFF_MS = 2000
const MAX_BACKOFF_MS = 30000

export function createRadarSocket({ onFrame, onStatusChange }) {
  let socket = null
  let reconnectTimer = null
  let backoff = BASE_BACKOFF_MS
  let closedByClient = false

  function scheduleReconnect() {
    if (closedByClient) return
    clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(connect, backoff)
    backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
  }

  function connect() {
    if (document.hidden) return // se reintenta en visibilitychange

    onStatusChange?.('connecting')

    try {
      socket = new WebSocket(WS_URL)
    } catch {
      scheduleReconnect()
      return
    }

    socket.onopen = () => {
      backoff = BASE_BACKOFF_MS
      onStatusChange?.('connected')
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'NEW_RADAR_FRAME') onFrame(data)
      } catch (err) {
        console.error('WS: mensaje inválido', err)
      }
    }

    socket.onerror = () => {
      onStatusChange?.('error')
    }

    socket.onclose = () => {
      onStatusChange?.('disconnected')
      scheduleReconnect()
    }
  }

  function handleVisibilityChange() {
    if (!document.hidden && (!socket || socket.readyState === WebSocket.CLOSED)) {
      backoff = BASE_BACKOFF_MS
      connect()
    }
  }

  function start() {
    closedByClient = false
    document.addEventListener('visibilitychange', handleVisibilityChange)
    connect()
  }

  function stop() {
    closedByClient = true
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    clearTimeout(reconnectTimer)
    socket?.close()
  }

  return { start, stop }
}
