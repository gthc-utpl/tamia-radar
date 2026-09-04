import { useMemo } from 'react'
import useStore from '../store/useStore'
import { ANIMATION_CONFIG } from '../config/radars'

/**
 * Reactive hook that returns the current frame data for each radar.
 * Subscribes to currentFrameIndex, frames, and radarFrames so MapView re-renders on each frame change.
 */
export function useCurrentFrame() {
  const animationActive = useStore((s) => s.animationActive)
  const currentFrameIndex = useStore((s) => s.currentFrameIndex)
  const frames = useStore((s) => s.frames)
  const radarFrames = useStore((s) => s.radarFrames)

  return useMemo(() => {
    if (!animationActive || frames.length === 0) return null

    const timestamp = frames[currentFrameIndex]
    if (!timestamp) return null

    const tolerance = ANIMATION_CONFIG.frameTolerance * 60 * 1000
    const result = { timestamp }

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
  }, [animationActive, currentFrameIndex, frames, radarFrames])
}
