import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import { calculateBounds } from '../../services/radarService'
import { getFreshness } from '../../utils/freshness'

export default function RadarOverlay({ record, radarId, opacity, visible, isLive }) {
  const map = useMap()
  const overlayRef = useRef(null)
  const prevUrlRef = useRef(null)

  useEffect(() => {
    return () => {
      if (overlayRef.current) {
        map.removeLayer(overlayRef.current)
        overlayRef.current = null
      }
    }
  }, [map])

  useEffect(() => {
    const freshness = record ? getFreshness(record.timestamp) : 'no-data'
    const shouldHide = !record || !visible || (isLive && freshness === 'offline')

    if (shouldHide) {
      if (overlayRef.current) {
        map.removeLayer(overlayRef.current)
        overlayRef.current = null
        prevUrlRef.current = null
      }
      return
    }

    const bounds = calculateBounds(radarId, record)
    const effectiveOpacity = isLive && freshness === 'stale'
      ? (opacity * 0.6) / 100
      : opacity / 100

    if (overlayRef.current) {
      if (prevUrlRef.current !== record.url) {
        overlayRef.current.setUrl(record.url)
        prevUrlRef.current = record.url
      }
      overlayRef.current.setBounds(bounds)
      overlayRef.current.setOpacity(effectiveOpacity)
    } else {
      overlayRef.current = L.imageOverlay(record.url, bounds, {
        opacity: effectiveOpacity,
        interactive: false,
        className: 'radar-overlay-image',
      }).addTo(map)
      prevUrlRef.current = record.url
    }
  }, [record, radarId, visible, opacity, isLive, map])

  return null
}
