import { useCallback, useState, useEffect } from 'react'
import useStore from '../../store/useStore'
import { useGeolocation } from '../../hooks/useGeolocation'
import { useRadarData } from '../../hooks/useRadarData'

function FAB({ onClick, icon, label, active = false }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center
        shadow-lg transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-gray-900
        touch-manipulation active:scale-95
        ${active
          ? 'bg-blue-500 text-white hover:bg-blue-600 shadow-blue-500/30'
          : 'bg-white text-gray-700 hover:bg-gray-50 hover:shadow-xl'
        }`}
    >
      <i className={`fas ${icon} text-base sm:text-lg`} />
    </button>
  )
}

export default function FABs({ mapRef }) {
  const animationActive = useStore((s) => s.animationActive)
  const setAnimationActive = useStore((s) => s.setAnimationActive)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  const customDate = useStore((s) => s.customDate)
  const period = useStore((s) => s.period)
  const toggleSidebar = useStore((s) => s.toggleSidebar)
  const userLocation = useStore((s) => s.userLocation)
  const addToast = useStore((s) => s.addToast)

  const { startWatching } = useGeolocation()
  const { loadLatest, loadAnimationData, refreshAnimationFrames } = useRadarData()

  const [barHeight, setBarHeight] = useState(0)

  useEffect(() => {
    const handler = (e) => setBarHeight(e.detail.height || 0)
    window.addEventListener('animbar-resize', handler)
    return () => window.removeEventListener('animbar-resize', handler)
  }, [])

  const handleToggleAnimation = useCallback(() => {
    if (animationActive) setIsPlaying(false)
    setAnimationActive(!animationActive)
  }, [animationActive, setAnimationActive, setIsPlaying])

  const handleRefresh = useCallback(() => {
    if (!animationActive) {
      loadLatest()
      addToast('Datos actualizados', 'success')
    } else if (!customDate) {
      // Live mode — incremental refresh with current time
      refreshAnimationFrames(period)
    } else {
      // Custom date mode — reload same period
      loadAnimationData(new Date(customDate), period)
    }
  }, [animationActive, customDate, period, loadLatest, loadAnimationData, refreshAnimationFrames, addToast])

  const handleLocation = useCallback(() => {
    startWatching()
    if (userLocation && mapRef?.current) {
      mapRef.current.flyTo([userLocation.lat, userLocation.lon], 10, { duration: 1 })
    }
  }, [startWatching, userLocation, mapRef])

  return (
    <div
      className="fixed right-3 flex flex-col gap-2.5 z-[999]
        transition-[bottom] duration-300 ease-in-out"
      style={{ bottom: `${barHeight + 16}px` }}
    >
      <FAB
        onClick={handleToggleAnimation}
        icon="fa-film"
        label={animationActive ? 'Desactivar animación' : 'Activar animación'}
        active={animationActive}
      />
      <FAB onClick={handleRefresh} icon="fa-sync-alt" label="Actualizar datos" />
      <FAB onClick={handleLocation} icon="fa-location-arrow" label="Mi ubicación" active={!!userLocation} />
      <FAB onClick={toggleSidebar} icon="fa-cog" label="Configuración" />
    </div>
  )
}
