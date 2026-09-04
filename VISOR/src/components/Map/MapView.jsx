import { useEffect, useMemo, useRef } from 'react'
import {
  MapContainer,
  TileLayer,
  Circle,
  Marker,
  Popup,
  CircleMarker,
  useMap,
} from 'react-leaflet'
import L from 'leaflet'
import useStore from '../../store/useStore'
import { RADARS, MAP_CONFIG, BASE_LAYERS } from '../../config/radars'
import { useCurrentFrame } from '../../hooks/useCurrentFrame'
import RadarOverlay from './RadarOverlay'

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Fix Leaflet default icon issue in bundlers
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

function createRadarIcon(color) {
  return L.divIcon({
    className: 'radar-marker-icon',
    html: `<div style="
      width: 30px; height: 30px;
      border-radius: 50%;
      background: white;
      border: 3px solid ${color};
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    "><i class="fas fa-broadcast-tower" style="color:${color};font-size:12px"></i></div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

function BaseLayerSwitcher() {
  const map = useMap()
  const activeBaseLayer = useStore((s) => s.activeBaseLayer)
  const layerRef = useRef(null)

  useEffect(() => {
    const cfg = BASE_LAYERS[activeBaseLayer]
    if (layerRef.current) {
      map.removeLayer(layerRef.current)
    }
    layerRef.current = L.tileLayer(cfg.url, {
      attribution: cfg.attribution,
    }).addTo(map)

    return () => {
      if (layerRef.current) map.removeLayer(layerRef.current)
    }
  }, [activeBaseLayer, map])

  return null
}

function UserLocationLayer() {
  const userLocation = useStore((s) => s.userLocation)

  if (!userLocation) return null

  return (
    <>
      <Circle
        center={[userLocation.lat, userLocation.lon]}
        radius={userLocation.accuracy}
        pathOptions={{
          color: '#4285F4',
          fillColor: '#4285F4',
          fillOpacity: 0.1,
          weight: 1,
        }}
      />
      <CircleMarker
        center={[userLocation.lat, userLocation.lon]}
        radius={6}
        pathOptions={{
          color: '#fff',
          fillColor: '#4285F4',
          fillOpacity: 1,
          weight: 2,
        }}
      />
    </>
  )
}

function MapEventHandler({ mapRef }) {
  const map = useMap()
  useEffect(() => {
    if (mapRef) mapRef.current = map
  }, [map, mapRef])
  return null
}

export default function MapView({ mapRef }) {
  const radarVisibility = useStore((s) => s.radarVisibility)
  const radarOpacity = useStore((s) => s.radarOpacity)
  const showMarkers = useStore((s) => s.showMarkers)
  const showCoverage = useStore((s) => s.showCoverage)
  const latestRecords = useStore((s) => s.latestRecords)
  const animationActive = useStore((s) => s.animationActive)
  const frameData = useCurrentFrame()

  const radarEntries = useMemo(() => Object.entries(RADARS), [])

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640
  const initialZoom = isMobile ? MAP_CONFIG.defaultZoom - 1 : MAP_CONFIG.defaultZoom

  return (
    <MapContainer
      center={MAP_CONFIG.center}
      zoom={initialZoom}
      minZoom={MAP_CONFIG.minZoom}
      maxZoom={MAP_CONFIG.maxZoom}
      className="w-full h-full z-0"
      zoomControl={false}
    >
      <MapEventHandler mapRef={mapRef} />
      <BaseLayerSwitcher />

      {radarEntries.map(([id, radar]) => (
        <Circle
          key={`coverage-${id}`}
          center={[radar.lat, radar.lon]}
          radius={radar.coverageKm * 1000}
          pathOptions={{
            color: radar.colorHex,
            fillColor: radar.colorHex,
            fillOpacity: showCoverage ? 0.03 : 0,
            weight: 1,
            dashArray: '5, 10',
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong style={{ color: radar.colorHex }}>{radar.name}</strong>
              <span className="text-gray-500"> — {radar.location}</span>
              <br />
              Cobertura: {radar.coverageKm} km
              <br />
              Resolución: {radar.resolution}
              <br />
              Actualización: {radar.frequency}
              <br />
              Coords: {radar.lat.toFixed(4)}°, {radar.lon.toFixed(4)}°
            </div>
          </Popup>
        </Circle>
      ))}

      {showMarkers &&
        radarEntries.map(([id, radar]) => (
          <Marker
            key={`marker-${id}`}
            position={[radar.lat, radar.lon]}
            icon={createRadarIcon(radar.colorHex)}
          >
            <Popup>
              <div className="text-sm">
                <strong>{radar.name}</strong> - {radar.location}
                <br />
                Cobertura: {radar.coverageKm} km
                <br />
                Resolución: {radar.resolution}
                <br />
                Coords: {radar.lat.toFixed(4)}, {radar.lon.toFixed(4)}
              </div>
            </Popup>
          </Marker>
        ))}

      {radarEntries.map(([id]) => {
        const record = animationActive
          ? frameData?.[id]
          : latestRecords[id]

        return (
          <RadarOverlay
            key={`overlay-${id}`}
            radarId={id}
            record={record}
            opacity={radarOpacity}
            visible={radarVisibility[id]}
          />
        )
      })}

      <UserLocationLayer />
    </MapContainer>
  )
}
