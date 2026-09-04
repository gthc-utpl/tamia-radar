import { create } from 'zustand'
import { ANIMATION_CONFIG } from '../config/radars'

const useStore = create((set, get) => ({
  // Radar state
  radarVisibility: { guaxx: true, loxx: true },
  radarOpacity: 100,
  showMarkers: false,
  showCoverage: false,
  latestRecords: { guaxx: null, loxx: null },
  activeBaseLayer: 'osm',

  // Animation state
  animationActive: false,
  isPlaying: false,
  currentFrameIndex: 0,
  period: ANIMATION_CONFIG.defaultPeriod,
  speed: ANIMATION_CONFIG.defaultSpeed,
  frames: [],         // unified timeline of timestamps
  radarFrames: {},     // { guaxx: [...records], loxx: [...records] }
  customDate: null,
  useCustomDate: false,

  // Loading state
  isLoading: false,
  loadingMessage: '',
  preloadProgress: null, // { loaded, errors, total }

  // UI state
  sidebarOpen: false,
  legendMinimized: false,
  toasts: [],

  // Location state
  userLocation: null,
  locationWatchId: null,

  // Actions - Radar
  setRadarVisibility: (radarId, visible) =>
    set((s) => ({
      radarVisibility: { ...s.radarVisibility, [radarId]: visible },
    })),

  setRadarOpacity: (opacity) => set({ radarOpacity: opacity }),
  setShowMarkers: (show) => set({ showMarkers: show }),
  setShowCoverage: (show) => set({ showCoverage: show }),
  setLatestRecord: (radarId, record) =>
    set((s) => ({
      latestRecords: { ...s.latestRecords, [radarId]: record },
    })),
  setActiveBaseLayer: (layer) => set({ activeBaseLayer: layer }),

  // Actions - Animation
  setAnimationActive: (active) => set({ animationActive: active }),
  setIsPlaying: (playing) => set({ isPlaying: playing }),
  setCurrentFrameIndex: (index) => set({ currentFrameIndex: index }),
  setPeriod: (period) => set({ period }),
  setSpeed: (speed) => set({ speed }),
  setFrames: (frames) => set({ frames }),
  setRadarFrames: (radarFrames) => set({ radarFrames }),
  setCustomDate: (date) => set({ customDate: date }),
  setUseCustomDate: (use) => set({ useCustomDate: use }),

  // Actions - Loading
  setIsLoading: (loading, message) =>
    set({ isLoading: loading, loadingMessage: message || '' }),
  setPreloadProgress: (progress) => set({ preloadProgress: progress }),

  // Actions - UI
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setLegendMinimized: (min) => set({ legendMinimized: min }),

  addToast: (message, type = 'info', duration = 3000) => {
    const id = Date.now()
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }))
    if (duration > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
      }, duration)
    }
    return id
  },
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  // Actions - Location
  setUserLocation: (loc) => set({ userLocation: loc }),
  setLocationWatchId: (id) => set({ locationWatchId: id }),

  // Computed-like helpers
  getCurrentFrameData: () => {
    const { currentFrameIndex, frames, radarFrames } = get()
    if (frames.length === 0) return null

    const timestamp = frames[currentFrameIndex]
    if (!timestamp) return null

    const result = { timestamp }
    const tolerance = ANIMATION_CONFIG.frameTolerance * 60 * 1000

    for (const [radarId, records] of Object.entries(radarFrames)) {
      let closest = null
      let minDiff = Infinity
      for (const record of records) {
        const diff = Math.abs(record.timestamp - timestamp)
        if (diff < minDiff && diff <= tolerance) {
          minDiff = diff
          closest = record
        }
      }
      result[radarId] = closest
    }

    return result
  },
}))

export default useStore
