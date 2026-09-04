# database.py - Conexión a la Base de Datos (SQLAlchemy 2.x)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Ajusta esta URL con tus credenciales reales (PostgreSQL o Supabase en el futuro)
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg://usuario:password@localhost:5432/radar_db"
)

# Crear el motor de la base de datos
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Crear la sesión de trabajo
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base moderna para los modelos ORM (SQLAlchemy 2.x)
class Base(DeclarativeBase):
    pass
