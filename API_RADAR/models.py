# models.py - Modelos de la Base de Datos
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Float, 
    DateTime, 
    ForeignKey, 
    BigInteger, 
    JSON, 
    Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

# Tabla de Catálogo de Radares
class Radar(Base):
    __tablename__ = "radars"
    
    id = Column(String(20), primary_key=True, index=True) # loxx, guaxx
    name = Column(String(100), nullable=False)
    location = Column(String(100))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    coverage_km = Column(Integer)
    data_path = Column(String(255))
    color_hex = Column(String(7))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relación uno-a-muchos con los frames
    frames = relationship("RadarFrame", back_populates="radar")

# Tabla de Registro de Frames (Reemplazo de index.json)
class RadarFrame(Base):
    __tablename__ = "radar_frames"
    
    id = Column(Integer, primary_key=True, index=True)
    radar_id = Column(String(20), ForeignKey("radars.id"))
    filename = Column(String(255), nullable=False)
    relative_path = Column(String, nullable=False)
    timestamp_local = Column(DateTime, nullable=False, index=True)
    timestamp_utc = Column(DateTime, nullable=False)
    size_bytes = Column(BigInteger)
    data_type = Column(String(20), default="DBZH")
    
    # Metadata geográfica
    bounds = Column(JSON) # JSONB en PostgreSQL (SQLAlchemy JSON mapea automáticamente)
    center = Column(JSON)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relación inversa con el radar
    radar = relationship("Radar", back_populates="frames")
