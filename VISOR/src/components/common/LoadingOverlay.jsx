import useStore from '../../store/useStore'

export default function LoadingOverlay() {
  const isLoading = useStore((s) => s.isLoading)
  const loadingMessage = useStore((s) => s.loadingMessage)
  const preloadProgress = useStore((s) => s.preloadProgress)
  const animationActive = useStore((s) => s.animationActive)

  // Only show full overlay on initial load, not during animation preload
  if (!isLoading || animationActive) return null

  const percent = preloadProgress
    ? Math.round((preloadProgress.loaded / preloadProgress.total) * 100)
    : null

  return (
    <div className="fixed inset-0 z-[3000] bg-[#1e478e]/90 backdrop-blur-sm flex flex-col items-center justify-center gap-4">
      <div className="w-12 h-12 border-4 border-white/20 border-t-white rounded-full animate-spin" />
      <p className="text-white text-sm font-medium">{loadingMessage}</p>
      {percent !== null && (
        <div className="w-48">
          <div className="h-1.5 bg-white/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-white rounded-full transition-[width] duration-200"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-white/70 text-xs text-center mt-1">{percent}%</p>
        </div>
      )}
    </div>
  )
}
