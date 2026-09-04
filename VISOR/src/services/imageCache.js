import { ANIMATION_CONFIG } from '../config/radars'

class LRUCache {
  constructor(maxSize = ANIMATION_CONFIG.maxCacheSize) {
    this.maxSize = maxSize
    this.cache = new Map()
  }

  get(key) {
    if (!this.cache.has(key)) return null
    const value = this.cache.get(key)
    this.cache.delete(key)
    this.cache.set(key, value)
    return value
  }

  set(key, value) {
    if (this.cache.has(key)) {
      this.cache.delete(key)
    } else if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value
      this.cache.delete(firstKey)
    }
    this.cache.set(key, value)
  }

  has(key) {
    return this.cache.has(key)
  }

  clear() {
    this.cache.clear()
  }

  get size() {
    return this.cache.size
  }
}

const imageCache = new LRUCache()
let activeController = null

export function abortPendingLoads() {
  if (activeController) {
    activeController.abort()
    activeController = null
  }
}

export async function preloadImage(url) {
  if (imageCache.has(url)) {
    return imageCache.get(url)
  }

  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imageCache.set(url, img)
      resolve(img)
    }
    img.onerror = () => reject(new Error(`Failed to load: ${url}`))
    img.src = url
  })
}

export async function preloadBatch(urls, onProgress, signal) {
  const { batchSize } = ANIMATION_CONFIG
  let loaded = 0
  let errors = 0

  for (let i = 0; i < urls.length; i += batchSize) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

    const batch = urls.slice(i, i + batchSize)
    const results = await Promise.allSettled(
      batch.map((url) => preloadImage(url))
    )

    results.forEach((r) => {
      if (r.status === 'fulfilled') loaded++
      else errors++
    })

    onProgress?.({ loaded, errors, total: urls.length })
  }

  return { loaded, errors, total: urls.length }
}

export function startPreload(urls, onProgress) {
  abortPendingLoads()
  activeController = new AbortController()

  return preloadBatch(urls, onProgress, activeController.signal)
}

export function isImageCached(url) {
  return imageCache.has(url)
}

export function clearImageCache() {
  imageCache.clear()
}

export default imageCache
