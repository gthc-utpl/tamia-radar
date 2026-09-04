import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import { calculateBounds } from '../../services/radarService'

export default function RadarOverlay({ record, radarId, opacity, visible }) {
  const map = useMap()
  const overlayRef = useRef(null)
  const prevUrlRef = useRef(null)

  // Create/destroy the layer based on visibility
  useEffect(() => {
    return () => {
      if (overlayRef.current) {
        map.removeLayer(overlayRef.current)
        overlayRef.current = null
      }
    }
  }, [map])

  // Update the overlay when record/visibility changes
  useEffect(() => {
    if (!record || !visible) {
      if (overlayRef.current) {
        map.removeLayer(overlayRef.current)
        overlayRef.current = null
        prevUrlRef.current = null
      }
      return
    }

    const bounds = calculateBounds(radarId, record)

    if (overlayRef.current) {
      // Update existing overlay — only change URL if it actually changed
      if (prevUrlRef.current !== record.url) {
        overlayRef.current.setUrl(record.url)
        prevUrlRef.current = record.url
      }
      overlayRef.current.setBounds(bounds)
      overlayRef.current.setOpacity(opacity / 100)
    } else {
      // Create new overlay
      overlayRef.current = L.imageOverlay(record.url, bounds, {
        opacity: opacity / 100,
        interactive: false,
        className: 'radar-overlay-image',
      }).addTo(map)
      prevUrlRef.current = record.url
    }
  }, [record, radarId, visible, opacity, map])

  return null
}
