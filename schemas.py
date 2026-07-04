from pydantic import BaseModel, Field
from typing import Optional
from typing import List

# Schema untuk mendefinisikan aturan saat membuat SENSOR baru
class SensorCreate(BaseModel):
    sensor_name: str = Field(..., max_length=50, example="DHT22 - Temp")
    location: str = Field(..., max_length=50, example="Greenhouse D")

# Schema untuk mendefinisikan aturan saat membuat BACAAN SENSOR (Readings) baru
class ReadingCreate(BaseModel):
    sensor_id: int = Field(..., example=1)
    value: float = Field(..., example=25.40)

class SensorUpdate(BaseModel):
    sensor_name: Optional[str] = None
    location: Optional[str] = None
    
# Masukkan ke bagian paling bawah schemas.py
class ReadingResponse(BaseModel):
    id: int
    sensor_id: int
    value: float

    class Config:
        from_attributes = True  # Mengizinkan Pydantic membaca objek SQLAlchemy

class PaginatedReadings(BaseModel):
    total_data: int
    halaman_sekarang: int
    total_halaman: int
    data: List[ReadingResponse]
    
class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "researcher" # Default sebagai researcher untuk analisis data

class Token(BaseModel):
    access_token: str
    token_type: str