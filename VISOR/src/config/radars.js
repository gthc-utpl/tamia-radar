export const RADARS = {
  guaxx: {
    id: 'guaxx',
    name: 'GUAXX',
    location: 'Celica',
    // Coordenadas UTM: 625225, 9553840 (EPSG:32717) → WGS84
    lat: -4.0333,
    lon: -79.8667,
    coverageKm: 100,
    dataPath: 'data/guaxx',
    color: 'rgba(255, 165, 0, 0.7)',
    colorHex: '#FFA500',
    scaleFactor: 1,
    zIndex: 201,
    resolution: '250m',
    frequency: '5 min',
  },
  loxx: {
    id: 'loxx',
    name: 'LOXX',
    location: 'Loja',
    // Coordenadas UTM: 705920, 9558850 (EPSG:32717) → WGS84
    lat: -3.989060,
    lon: -79.145308,
    coverageKm: 70,
    dataPath: 'data/loxx',
    color: 'rgba(30, 144, 255, 0.7)',
    colorHex: '#1E90FF',
    // scaleFactor removido (ahora los bounds vienen directos de la API)
    scaleFactor: 1,
    zIndex: 200,
    resolution: '250m',
    frequency: '5 min',
  },
}

export const MAP_CONFIG = {
  center: [-4.01, -79.5],
  defaultZoom: 9,
  minZoom: 7,
  maxZoom: 12,
}

export const ANIMATION_CONFIG = {
  periods: [
    { value: 1, label: '1h' },
    { value: 2, label: '2h' },
    { value: 4, label: '4h' },
  ],
  speeds: [
    { value: 0.5, label: '0.5x' },
    { value: 1, label: '1x' },
    { value: 2, label: '2x' },
    { value: 4, label: '4x' },
  ],
  defaultSpeed: 2,
  defaultPeriod: 4,
  batchSize: 10,
  frameTolerance: 10, // minutes
  maxCacheSize: 100,
  baseInterval: 1000, // ms at 1x speed
  autoRefreshInterval: 3 * 60 * 1000, // ms — auto-refresh during live animation
}

// Escala de reflectividad OFICIAL Furuno WR110 (familia jet), 10-70 dBZ paso 5,
// MÁS una clase inferior 8-10 dBZ (navy) para que el piso de la leyenda coincida
// con el umbral de ruido calibrado del nodo (MIN_DBZH_THRESHOLD = 8 dBZ).
// IMPORTANTE: estos hex DEBEN ser idénticos al LUT del nodo (DBZH_COLORS en
// EDGE/LOXX/.../generar_png_loxx.py) y de GUAXX. Si cambia uno, cambiar el otro.
export const DBZ_LEGEND = [
  { range: '8-10', color: '#000080', description: 'Muy débil' },
  { range: '10-15', color: '#0000B4', description: 'Débil' },
  { range: '15-20', color: '#0060FF', description: 'Ligera' },
  { range: '20-25', color: '#00C8F0', description: 'Ligera-moderada' },
  { range: '25-30', color: '#00E0A0', description: 'Moderada baja' },
  { range: '30-35', color: '#00C800', description: 'Moderada' },
  { range: '35-40', color: '#80E000', description: 'Moderada-fuerte' },
  { range: '40-45', color: '#FFF000', description: 'Fuerte' },
  { range: '45-50', color: '#FFC000', description: 'Muy fuerte' },
  { range: '50-55', color: '#FF8000', description: 'Intensa' },
  { range: '55-60', color: '#FF3800', description: 'Muy intensa' },
  { range: '60-65', color: '#E00000', description: 'Extrema' },
  { range: '65-70', color: '#900000', description: 'Extrema / granizo' },
]

export const BASE_LAYERS = {
  osm: {
    name: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
  dark: {
    name: 'CartoDB Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CartoDB',
  },
  light: {
    name: 'CartoDB Positron',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CartoDB',
  },
}
