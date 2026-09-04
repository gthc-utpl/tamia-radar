import { useCallback } from 'react'
import useStore from '../store/useStore'
import { RADARS } from '../config/radars'
import {
  fetchLatestRecord,
  fetchRecordsForPeriod,
  getAllImageUrls,
} from '../services/radarService'
import { startPreload, abortPendingLoads, preloadBatch } from '../services/imageCache'

export function useRadarData() {
  const setLatestRecord = useStore((s) => s.setLatestRecord)
  const setIsLoading = useStore((s) => s.setIsLoading)
  const setPreloadProgress = useStore((s) => s.setPreloadProgress)
  const setFrames = useStore((s) => s.setFrames)
  const setRadarFrames = useStore((s) => s.setRadarFrames)
  const setCurrentFrameIndex = useStore((s) => s.setCurrentFrameIndex)
  const addToast = useStore((s) => s.addToast)

  const loadLatest = useCallback(async () => {
    setIsLoading(true, 'Cargando datos más recientes...')
    const radarIds = Object.keys(RADARS)

    try {
      const results = await Promise.allSettled(
        radarIds.map((id) => fetchLatestRecord(id))
      )

      results.forEach((result, i) => {
        if (result.status === 'fulfilled' && result.value) {
          setLatestRecord(radarIds[i], result.value)
        }
      })

      const loaded = results.filter(
        (r) => r.status === 'fulfilled' && r.value
      ).length
      if (loaded === 0) {
        addToast('No se encontraron datos recientes', 'warning')
      }
    } catch (err) {
      addToast('Error al cargar datos: ' + err.message, 'error')
    } finally {
      setIsLoading(false)
    }
  }, [setLatestRecord, setIsLoading, addToast])

  const loadAnimationData = useCallback(
    async (endDate, hoursBack) => {
      setIsLoading(true, 'Cargando datos para animación...')
      abortPendingLoads()

      const radarIds = Object.keys(RADARS)

      try {
        const allRadarRecords = {}
        const timestampSet = new Set()

        const results = await Promise.allSettled(
          radarIds.map((id) => fetchRecordsForPeriod(id, endDate, hoursBack))
        )

        results.forEach((result, i) => {
          if (result.status === 'fulfilled') {
            allRadarRecords[radarIds[i]] = result.value
            result.value.forEach((r) => timestampSet.add(r.timestamp.getTime()))
          } else {
            allRadarRecords[radarIds[i]] = []
          }
        })

        const timestamps = Array.from(timestampSet)
          .sort((a, b) => a - b)
          .map((t) => new Date(t))

        if (timestamps.length === 0) {
          addToast('No hay datos disponibles para el periodo seleccionado', 'warning')
          setIsLoading(false)
          return
        }

        setRadarFrames(allRadarRecords)
        setFrames(timestamps)
        setCurrentFrameIndex(0)

        // Preload images
        setIsLoading(true, 'Precargando imágenes...')
        const allUrls = radarIds.flatMap((id) =>
          getAllImageUrls(allRadarRecords[id] || [])
        )

        if (allUrls.length > 0) {
          await startPreload(allUrls, (progress) => {
            setPreloadProgress(progress)
          })
        }

        setPreloadProgress(null)
        addToast(
          `${timestamps.length} frames cargados correctamente`,
          'success'
        )
      } catch (err) {
        if (err.name !== 'AbortError') {
          addToast('Error al cargar animación: ' + err.message, 'error')
        }
      } finally {
        setIsLoading(false)
      }
    },
    [setIsLoading, setRadarFrames, setFrames, setCurrentFrameIndex, setPreloadProgress, addToast]
  )

  const refreshAnimationFrames = useCallback(
    async (hoursBack) => {
      const radarIds = Object.keys(RADARS)
      const now = new Date()

      try {
        const allRadarRecords = {}
        const timestampSet = new Set()

        const results = await Promise.allSettled(
          radarIds.map((id) => fetchRecordsForPeriod(id, now, hoursBack))
        )

        results.forEach((result, i) => {
          if (result.status === 'fulfilled') {
            allRadarRecords[radarIds[i]] = result.value
            result.value.forEach((r) => timestampSet.add(r.timestamp.getTime()))
          } else {
            allRadarRecords[radarIds[i]] = []
          }
        })

        const newTimestamps = Array.from(timestampSet)
          .sort((a, b) => a - b)
          .map((t) => new Date(t))

        if (newTimestamps.length === 0) return

        // Compare with existing timeline — skip update if identical
        const { frames: oldFrames, currentFrameIndex, radarFrames: oldRadarFrames } = useStore.getState()
        const oldKeys = oldFrames.map((t) => t.getTime()).join(',')
        const newKeys = newTimestamps.map((t) => t.getTime()).join(',')
        if (oldKeys === newKeys) return

        // Preserve the timestamp the user is currently viewing
        const currentTimestamp = oldFrames[currentFrameIndex]?.getTime()

        // Update store
        setRadarFrames(allRadarRecords)
        setFrames(newTimestamps)

        // Find closest index to the previously displayed timestamp
        if (currentTimestamp != null) {
          let bestIdx = 0
          let bestDiff = Infinity
          newTimestamps.forEach((t, i) => {
            const diff = Math.abs(t.getTime() - currentTimestamp)
            if (diff < bestDiff) { bestDiff = diff; bestIdx = i }
          })
          setCurrentFrameIndex(bestIdx)
        }

        // Preload only new images (ones not already cached)
        const oldUrlSet = new Set(
          radarIds.flatMap((id) => getAllImageUrls(oldRadarFrames[id] || []))
        )
        const newUrls = radarIds
          .flatMap((id) => getAllImageUrls(allRadarRecords[id] || []))
          .filter((url) => !oldUrlSet.has(url))

        if (newUrls.length > 0) {
          // Background preload — no abort of existing loads, no progress overlay
          await preloadBatch(newUrls)
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          addToast('Error al actualizar frames: ' + err.message, 'error')
        }
      }
    },
    [setRadarFrames, setFrames, setCurrentFrameIndex, addToast]
  )

  return { loadLatest, loadAnimationData, refreshAnimationFrames }
}
