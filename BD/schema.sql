-- Esquema SQL de TAMIA (Tropical Andean Meteorological Imaging Architecture)
-- Ubicación en el repositorio: BD/schema.sql

-- 1. Catálogo de radares
-- Tabla para almacenar la configuración básica y estática de los radares
CREATE TABLE IF NOT EXISTS radars (
    id VARCHAR(20) PRIMARY KEY,        -- 'loxx', 'guaxx'
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    coverage_km INTEGER,
    data_path VARCHAR(255),            -- ej: 'data/loxx'
    color_hex VARCHAR(7),              -- Color asignado para visualización
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Registro de frames (imágenes procesadas)
-- Tabla que reemplaza el archivo index.json diario por una base de datos centralizada
CREATE TABLE IF NOT EXISTS radar_frames (
    id SERIAL PRIMARY KEY,
    radar_id VARCHAR(20) REFERENCES radars(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    relative_path TEXT NOT NULL,       -- Ruta relativa: 'loxx/2026/090/radar_loxx_...'
    timestamp_local TIMESTAMP NOT NULL, -- Hora local de Ecuador (UTC-5)
    timestamp_utc TIMESTAMP NOT NULL,
    size_bytes BIGINT,                 -- Tamaño del archivo en bytes
    data_type VARCHAR(20) DEFAULT 'DBZH',
    
    -- Metadatos geográficos (se almacenan por frame en caso de cambios o rectificaciones)
    -- Estructura: [[latMin, lonMin], [latMax, lonMax]]
    bounds JSONB, 
    center JSONB,                      -- [lat, lon] (orden Leaflet; igual que 'bounds')
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para búsqueda rápida (Fundamentales para la animación y consultas temporales)
CREATE INDEX IF NOT EXISTS idx_radar_frames_timestamp ON radar_frames (timestamp_local DESC);
CREATE INDEX IF NOT EXISTS idx_radar_frames_radar_id ON radar_frames (radar_id);

-- 3. Insertar radares iniciales (Datos extraídos de la configuración actual)
INSERT INTO radars (id, name, location, latitude, longitude, coverage_km, data_path, color_hex)
VALUES 
('loxx', 'Radar Loja (LOXX)', 'Loja', -3.989060, -79.145308, 70, 'data/loxx', '#1E90FF'),
('guaxx', 'Radar Celica (GUAXX)', 'Celica', -4.0333, -79.8667, 100, 'data/guaxx', '#FFA500')
ON CONFLICT (id) DO UPDATE SET 
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    coverage_km = EXCLUDED.coverage_km;


UPDATE radars SET latitude = -3.989060, longitude = -79.145308 WHERE id = 'loxx';