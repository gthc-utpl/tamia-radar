# main.py - API central de TAMIA (tiempo real)
# Incluye: WebSockets, filtro temporal, API Key y schemas Pydantic.

from fastapi import (
    FastAPI, 
    Depends, 
    UploadFile, 
    File, 
    HTTPException, 
    Form, 
    WebSocket, 
    WebSocketDisconnect,
    Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import shutil
from pathlib import Path

# Importar lógica de Base de Datos
from database import SessionLocal, engine
import models

# Asegurar carpetas de almacenamiento para las imágenes
UPLOAD_DIR = Path("data/radar")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Crear tablas en DB si no existen
models.Base.metadata.create_all(bind=engine)

# API Key para proteger el endpoint de subida (configurar en .env).
# Sin valor por defecto real: si RADAR_API_KEY no está definido, se usa un
# placeholder no funcional para evitar exponer la clave en el código.
API_KEY = os.getenv("RADAR_API_KEY", "CHANGE_ME")

app = FastAPI(title="TAMIA Central API - Real Time", version="2.2.0")

# Habilitar CORS para que el Visor React pueda consultar la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir imágenes de radar como archivos estáticos
app.mount("/data", StaticFiles(directory="data"), name="static_data")


# ============================================================================
# SCHEMAS PYDANTIC (para serialización correcta de respuestas)
# ============================================================================

class RadarOut(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    latitude: float
    longitude: float
    coverage_km: Optional[int] = None
    data_path: Optional[str] = None
    color_hex: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True  # SQLAlchemy 2.x compatibility

class RadarFrameOut(BaseModel):
    id: int
    radar_id: str
    filename: str
    relative_path: str
    timestamp_local: datetime
    timestamp_utc: datetime
    size_bytes: Optional[int] = None
    data_type: str = "DBZH"
    bounds: Optional[list] = None
    center: Optional[list] = None

    class Config:
        from_attributes = True

# ============================================================================
# DEPENDENCIAS
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_api_key(x_api_key: str = Header(...)):
    """Verifica que el request del radar Edge tenga la clave correcta."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
    return x_api_key

# ============================================================================
# GESTOR DE CONEXIONES EN TIEMPO REAL (WEBSOCKETS)
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Acepta la conexión del Visor."""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Visor conectado. Total activos: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Elimina el Visor cuando se cierra la pestaña o pierde conexión."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"Visor desconectado. Total activos: {len(self.active_connections)}")

    async def broadcast_new_frame(self, message: dict):
        """Envía una notificación JSON a todos los Visores conectados."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Limpiar conexiones muertas
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

@app.websocket("/ws/radar/updates")
async def websocket_updates_endpoint(websocket: WebSocket):
    """Endpoint al que el Visor React se conectará vía WS."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ============================================================================
# ENDPOINTS DE LOS RADARES (UPLOAD / EDGE-RADAR)
# ============================================================================

@app.post("/upload/{radar_id}", status_code=201)
async def upload_radar_frame(
    radar_id: str,
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Recibe un PNG y su metadata. Protegido por API Key.
    Notifica automáticamente a los Visores vía WebSocket.
    """
    # 1. Verificar si el radar existe
    radar = db.query(models.Radar).filter(models.Radar.id == radar_id).first()
    if not radar:
        raise HTTPException(status_code=404, detail="Radar no registrado")

    # 2. Parsear metadata
    try:
        info = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Metadata JSON inválida")

    # 3. Extraer tipo de dato (Por defecto DBZH para compatibilidad hacia atrás)
    data_type = info.get('data_type', 'DBZH')

    # 4. Organizar archivo en disco físicamente
    ts_local = datetime.strptime(info['timestamp_local'], '%Y-%m-%d %H:%M:%S')
    year = ts_local.strftime('%Y')
    julian_day = ts_local.strftime('%j')
    
    # NUEVA ESTRUCTURA: radar_id / data_type / year / julian_day
    save_path = UPLOAD_DIR / radar_id / data_type / year / julian_day
    save_path.mkdir(parents=True, exist_ok=True)
    
    file_location = save_path / file.filename
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 5. Registrar en Base de Datos
    new_frame = models.RadarFrame(
        radar_id=radar_id,
        filename=file.filename,
        # La ruta relativa también incluye el data_type
        relative_path=f"radar/{radar_id}/{data_type}/{year}/{julian_day}/{file.filename}",
        timestamp_local=ts_local,
        timestamp_utc=datetime.strptime(info['timestamp_utc'], '%Y-%m-%d %H:%M:%S'),
        size_bytes=os.path.getsize(file_location),
        bounds=info.get('bounds'),
        center=info.get('center'),
        data_type=data_type
    )
    
    db.add(new_frame)
    db.commit()
    db.refresh(new_frame)

    # 5. NOTIFICACIÓN EN TIEMPO REAL
    await manager.broadcast_new_frame({
        "type": "NEW_RADAR_FRAME",
        "radar_id": radar_id,
        "radar_name": radar.name,
        "filename": new_frame.filename,
        "timestamp": new_frame.timestamp_local.strftime('%Y-%m-%d %H:%M:%S'),
        "url": f"/data/{new_frame.relative_path}",
        "bounds": new_frame.bounds
    })

    return {"status": "success", "file": file.filename}

# ============================================================================
# ENDPOINTS DEL VISOR (QUERY / REACT)
# ============================================================================

@app.get("/frames/{radar_id}", response_model=List[RadarFrameOut])
def get_recent_frames(
    radar_id: str, 
    hours_back: int = 4, 
    db: Session = Depends(get_db)
):
    """Obtiene los frames de las últimas N horas con filtro temporal REAL."""
    cutoff = datetime.now() - timedelta(hours=hours_back)
    
    frames = db.query(models.RadarFrame) \
               .filter(models.RadarFrame.radar_id == radar_id) \
               .filter(models.RadarFrame.timestamp_local >= cutoff) \
               .order_by(models.RadarFrame.timestamp_local.desc()) \
               .all()
    return frames

@app.get("/radars", response_model=List[RadarOut])
def get_system_radars(db: Session = Depends(get_db)):
    """Obtiene el catálogo de radares registrados."""
    return db.query(models.Radar).all()
