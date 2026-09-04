import { useEffect, useRef, useCallback } from 'react'
import useStore from '../store/useStore'
import { ANIMATION_CONFIG } from '../config/radars'

export function useAnimation() {
  const isPlaying = useStore((s) => s.isPlaying)
  const setIsPlaying = useStore((s) => s.setIsPlaying)
  const currentFrameIndex = useStore((s) => s.currentFrameIndex)
  const setCurrentFrameIndex = useStore((s) => s.setCurrentFrameIndex)
  const frames = useStore((s) => s.frames)
  const speed = useStore((s) => s.speed)

  const rafRef = useRef(null)
  const lastTimeRef = useRef(0)

  const totalFrames = frames.length

  const nextFrame = useCallback(() => {
    setCurrentFrameIndex(
      totalFrames > 0 ? (useStore.getState().currentFrameIndex + 1) % totalFrames : 0
    )
  }, [totalFrames, setCurrentFrameIndex])

  const prevFrame = useCallback(() => {
    setCurrentFrameIndex(
      totalFrames > 0
        ? (useStore.getState().currentFrameIndex - 1 + totalFrames) % totalFrames
        : 0
    )
  }, [totalFrames, setCurrentFrameIndex])

  const goToFirst = useCallback(() => setCurrentFrameIndex(0), [setCurrentFrameIndex])

  const goToLast = useCallback(
    () => setCurrentFrameIndex(Math.max(0, totalFrames - 1)),
    [totalFrames, setCurrentFrameIndex]
  )

  const togglePlay = useCallback(() => {
    setIsPlaying(!useStore.getState().isPlaying)
  }, [setIsPlaying])

  const seekTo = useCallback(
    (index) => {
      const clamped = Math.max(0, Math.min(index, totalFrames - 1))
      setCurrentFrameIndex(clamped)
    },
    [totalFrames, setCurrentFrameIndex]
  )

  // Animation loop using requestAnimationFrame
  useEffect(() => {
    if (!isPlaying || totalFrames === 0) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      return
    }

    const interval = ANIMATION_CONFIG.baseInterval / speed

    const animate = (time) => {
      if (time - lastTimeRef.current >= interval) {
        lastTimeRef.current = time
        const curr = useStore.getState().currentFrameIndex
        setCurrentFrameIndex((curr + 1) % totalFrames)
      }
      rafRef.current = requestAnimationFrame(animate)
    }

    lastTimeRef.current = performance.now()
    rafRef.current = requestAnimationFrame(animate)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [isPlaying, speed, totalFrames, setCurrentFrameIndex])

  // Pause on tab hidden
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden && isPlaying) {
        setIsPlaying(false)
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [isPlaying, setIsPlaying])

  return {
    nextFrame,
    prevFrame,
    goToFirst,
    goToLast,
    togglePlay,
    seekTo,
    totalFrames,
    currentFrameIndex,
    isPlaying,
  }
}
