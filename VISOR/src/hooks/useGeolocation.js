import { useCallback } from 'react'
import useStore from '../store/useStore'
import { RADARS } from '../config/radars'

function haversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function useGeolocation() {
  const setUserLocation = useStore((s) => s.setUserLocation)
  const setLocationWatchId = useStore((s) => s.setLocationWatchId)
  const locationWatchId = useStore((s) => s.locationWatchId)
  const addToast = useStore((s) => s.addToast)

  const startWatching = useCallback(() => {
    if (!navigator.geolocation) {
      addToast('Geolocalización no disponible en este navegador', 'error')
      return
    }

    if (locationWatchId !== null) return

    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const loc = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }

        // Check radar coverage
        let nearestRadar = null
        let minDist = Infinity
        for (const [radarId, radar] of Object.entries(RADARS)) {
          const dist = haversineDistance(loc.lat, loc.lon, radar.lat, radar.lon)
          if (dist < minDist) {
            minDist = dist
            nearestRadar = { radarId, distance: dist, inCoverage: dist <= radar.coverageKm }
          }
        }

        setUserLocation({ ...loc, nearestRadar })
      },
      (err) => {
        addToast('Error de ubicación: ' + err.message, 'warning')
      },
      { enableHighAccuracy: true, maximumAge: 30000 }
    )

    setLocationWatchId(id)
  }, [locationWatchId, setUserLocation, setLocationWatchId, addToast])

  const stopWatching = useCallback(() => {
    if (locationWatchId !== null) {
      navigator.geolocation.clearWatch(locationWatchId)
      setLocationWatchId(null)
    }
  }, [locationWatchId, setLocationWatchId])

  return { startWatching, stopWatching }
}
