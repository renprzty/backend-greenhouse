from sqlalchemy import Column, Integer, String, Float, Numeric, DateTime, ForeignKey
from database import Base

class Sensor(Base):
    __tablename__ = "sensors" # Harus sama persis dengan nama tabel di DBeaver

    id = Column(Integer, primary_key=True, index=True)
    sensor_name = Column(String(50), nullable=False)
    location = Column(String(50), nullable=False)
    status_baterai = Column(String(20), nullable=True)

class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"))
    value = Column(Numeric(5,2), nullable=False)
    # Kita tidak memasukkan created_at dulu agar tetap sederhana di awal
    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="researcher") # Pilihan: admin, researcher, device