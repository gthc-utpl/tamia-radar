// radarService.js - Adaptado para API REST GTHC (reemplaza lectura de index.json)
import { RADARS } from '../config/radars'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function fetchJson(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`)
  return res.json()
}

/**
 * Obtiene el frame más reciente de un radar directamente de la API/DB.
 */
export async function fetchLatestRecord(radarId) {
  try {
    const frames = await fetchJson(`${API_BASE}/frames/${radarId}?hours_back=1`)
    if (frames.length === 0) return null

    const latest = frames[0]
    return {
      ...latest,
      radarId,
      url: `${API_BASE}/data/${latest.relative_path}`,
      timestamp: new Date(latest.timestamp_local.replace(' ', 'T')),
    }
  } catch (error) {
    console.error(`Error en fetchLatestRecord (${radarId}):`, error)
    return null
  }
}

/**
 * Obtiene todos los frames para un periodo de animación usando la API/DB.
 */
export async function fetchRecordsForPeriod(radarId, endDate, hoursBack) {
  try {
    const frames = await fetchJson(`${API_BASE}/frames/${radarId}?hours_back=${hoursBack}`)

    return frames
      .map((record) => ({
        ...record,
        radarId,
        url: `${API_BASE}/data/${record.relative_path}`,
        timestamp: new Date(record.timestamp_local.replace(' ', 'T')),
      }))
      .sort((a, b) => a.timestamp - b.timestamp)
  } catch (error) {
    console.error(`Error en fetchRecordsForPeriod (${radarId}):`, error)
    return []
  }
}

/**
 * Calcula dinámicamente los bounds si no vienen en el record.
 * Con la nueva API, los bounds ya vienen por frame — este es solo un fallback.
 */
export function calculateBounds(radarId, record) {
  // Usar bounds del record si están disponibles (la API los envía siempre)
  if (record.bounds) return record.bounds

  // Fallback: calcular desde las coordenadas y cobertura del radar
  const radar = RADARS[radarId]
  const kmPerDegreeLat = 111.32
  const kmPerDegreeLon = kmPerDegreeLat * Math.cos((radar.lat * Math.PI) / 180)
  const latOffset = radar.coverageKm / kmPerDegreeLat
  const lonOffset = radar.coverageKm / kmPerDegreeLon

  return [
    [radar.lat - latOffset, radar.lon - lonOffset],
    [radar.lat + latOffset, radar.lon + lonOffset],
  ]
}

/**
 * Extrae todas las URLs de imágenes de una lista de records.
 */
export function getAllImageUrls(records) {
  return records.map((r) => r.url)
}
