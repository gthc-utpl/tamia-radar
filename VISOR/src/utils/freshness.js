import { RADAR_FRESHNESS } from '../config/radars'

export function getFreshness(timestamp, now = Date.now()) {
  if (!timestamp) return 'no-data'
  const ageMinutes = (now - new Date(timestamp).getTime()) / 60000
  if (ageMinutes < RADAR_FRESHNESS.freshMinutes) return 'fresh'
  if (ageMinutes < RADAR_FRESHNESS.staleMinutes) return 'stale'
  return 'offline'
}

export function formatAge(timestamp, now = Date.now()) {
  if (!timestamp) return null
  const diff = now - new Date(timestamp).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'ahora'
  if (mins < 60) return `hace ${mins} min`
  const hrs = Math.floor(mins / 60)
  const remainingMins = mins % 60
  if (hrs < 24) return remainingMins > 0 ? `hace ${hrs}h ${remainingMins}m` : `hace ${hrs}h`
  return `hace ${Math.floor(hrs / 24)}d`
}
