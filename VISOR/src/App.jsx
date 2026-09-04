import { useCallback, useEffect, useRef } from 'react'
import Header from './components/Header/Header'
import MapView from './components/Map/MapView'
import AnimationBar from './components/AnimationBar/AnimationBar'
import Sidebar from './components/Sidebar/Sidebar'
import ColorLegend from './components/ColorLegend/ColorLegend'
import FABs from './components/FABs/FABs'
import ToastContainer from './components/common/Toast'
import LoadingOverlay from './components/common/LoadingOverlay'
import useStore from './store/useStore'
import { useRadarData } from './hooks/useRadarData'

const AUTO_REFRESH_MS = 3 * 60 * 1000 // 3 minutes

export default function App() {
  const mapRef = useRef(null)
  const { loadLatest } = useRadarData()
  const animationActive = useStore((s) => s.animationActive)

  // Initial load
  useEffect(() => {
    loadLatest()
  }, [loadLatest])

  // Auto-refresh every 3 min when not in animation mode and tab is visible
  const refresh = useCallback(() => {
    if (!document.hidden) loadLatest()
  }, [loadLatest])

  useEffect(() => {
    if (animationActive) return
    const id = setInterval(refresh, AUTO_REFRESH_MS)
    return () => clearInterval(id)
  }, [animationActive, refresh])

  return (
    <div className="h-dvh flex flex-col bg-gray-900 overflow-hidden">
      <Header />

      {/* Map area */}
      <main className="flex-1 relative">
        <MapView mapRef={mapRef} />
        <ColorLegend />
        <FABs mapRef={mapRef} />
      </main>

      {/* Animation bar (bottom sheet) */}
      <AnimationBar />

      {/* Sidebar (drawer) */}
      <Sidebar />

      {/* Notifications */}
      <ToastContainer />
      <LoadingOverlay />
    </div>
  )
}
