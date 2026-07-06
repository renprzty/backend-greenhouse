import math
import pika
import models
import schemas
import redis
import json
import auth
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, get_db
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from auth import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from auth import get_password_hash
from datetime import timedelta


models.Base.metadata.create_all(bind=engine)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Koneksi ke Redis Server (Port default Redis adalah 6379)
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

@app.get("/")
def read_root():
    return {"status": "aktif", "pesan": "Backend Smart Greenhouse Berjalan Normal"}

# MODIFIKASI: Endpoint GET /sensors dengan Fitur Caching Redis
@app.get("/sensors")
def get_all_sensors(db: Session = Depends(get_db)):
    cache_key = "all_sensors"
    
    # 1. Cek apakah data sudah ada di papan pengumuman (Redis RAM)
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        # Cache Hit: Jika ada, langsung ubah teks JSON kembali menjadi data Python dan kirim
        print("=== DATA DIAMBIL DARI REDIS (CACHE HIT) ===")
        return json.loads(cached_data)
        
    # Cache Miss: Jika tidak ada di Redis, terpaksa ambil ke gudang arsip (PostgreSQL)
    print("=== DATA DIAMBIL DARI POSTGRESQL (CACHE MISS) ===")
    sensors = db.query(models.Sensor).all()
    
    # Karena data SQL berbentuk objek biner, kita ubah ke format teks JSON biasa agar bisa disimpan di Redis
    sensors_json = [{"id": s.id, "sensor_name": s.sensor_name, "location": s.location} for s in sensors]
    
    # 2. Simpan hasilnya ke Redis, beri waktu kedaluwarsa (TTL) selama 60 detik
    # Artinya, setelah 60 detik data di RAM otomatis terhapus agar jika ada update data baru tidak basi
    redis_client.setex(cache_key, 60, json.dumps(sensors_json))
    
    return sensors_json

# Endpoint POST /sensors (Harus menghapus cache agar data di RAM tidak basi saat ada sensor baru)
@app.post("/sensors", response_model=schemas.SensorCreate)
def create_sensor(
    sensor: schemas.SensorCreate, 
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
    ):
    db_sensor = models.Sensor(sensor_name=sensor.sensor_name, location=sensor.location)
    db.add(db_sensor)
    db.commit()
    db.refresh(db_sensor)
    
    # Evict Cache: Hapus catatan lama di Redis karena strukturnya sudah berubah ada sensor baru
    redis_client.delete("all_sensors")
    
    return db_sensor

# ... (Endpoint /sensor/{sensor_id} dan /readings dari Hari sebelumnya tetap biarkan di bawah)

@app.post("/register", status_code=201)
@limiter.limit("5/minute")
def register_user(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Cek duplikasi pengguna
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")
    
    # Enkripsi kata sandi menggunakan Bcrypt
    hashed_password = get_password_hash(user.password)
    
    # Simpan password yang sudah di-hash
    new_user = models.User(username=user.username, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User berhasil dibuat", "username": new_user.username}

@app.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    # Cari pengguna berdasarkan username (Sesuaikan query ini dengan model database Anda)
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # Verifikasi keberadaan pengguna dan kecocokan kata sandi
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Buat token jika valid
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint untuk mengambil data satu sensor berdasarkan ID-nya
@app.get("/sensor/{sensor_id}")
def get_sensor_data(sensor_id: int, db: Session = Depends(get_db)):
    # Setara dengan SQL: SELECT * FROM sensors WHERE id = sensor_id;
    sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor tidak ditemukan")
    
    return sensor

# Tambahkan ini di bagian paling bawah agar perangkat IoT tetap bisa mengirim data:
@app.post("/readings")
def create_reading(reading: schemas.ReadingCreate, db: Session = Depends(get_db)):
    sensor_exists = db.query(models.Sensor).filter(models.Sensor.id == reading.sensor_id).first()
    if not sensor_exists:
        raise HTTPException(status_code=400, detail="Gagal menyimpan: ID Sensor tidak terdaftar!")
        
    # 1. Simpan data ke PostgreSQL secara normal
    db_reading = models.Reading(
        sensor_id=reading.sensor_id,
        value=reading.value
    )
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)

    # 2. Kirim pesan antrean ke RabbitMQ (Pemrosesan Asinkron / Latar Belakang)
    try:
        credentials = pika.PlainCredentials('guest', 'guest')
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue='tugas_ai_greenhouse', durable=True)
        
        # Susun data yang akan dianalisis oleh worker
        pesan_tugas = {
            "reading_id": db_reading.id,
            "sensor_id": db_reading.sensor_id,
            "value": float(db_reading.value)
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='tugas_ai_greenhouse',
            body=json.dumps(pesan_tugas),
            properties=pika.BasicProperties(
                delivery_mode=2, # Membuat pesan persisten agar tidak hilang saat server restart
            ))
        connection.close()
    except Exception as e:
        print(f"Gagal terhubung ke RabbitMQ: {e}")

    return {
        "status": "sukses", 
        "data_tersimpan": reading,
        "pesan_sistem": "Data disimpan. Analisis AI sedang berjalan di latar belakang."
    }
# Tambahkan di bagian bawah main.py

# 1. Endpoint UPDATE (PATCH) untuk mengubah data sebagian
@app.patch("/sensors/{sensor_id}")
def update_sensor(sensor_id: int, updated_data: schemas.SensorUpdate, db: Session = Depends(get_db)):
    # Cari dulu sensornya ada atau tidak
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if not db_sensor:
        raise HTTPException(status_code=404, detail="Sensor tidak ditemukan")
    
    # Update hanya data yang dikirimkan oleh pengguna
    if updated_data.sensor_name is not None:
        db_sensor.sensor_name = updated_data.sensor_name
    if updated_data.location is not None:
        db_sensor.location = updated_data.location
        
    db.commit()
    db.refresh(db_sensor)
    
    # Hapus cache Redis karena data sudah berubah
    redis_client.delete("all_sensors")
    
    return {"status": "sukses diubah", "data_baru": db_sensor}

# 2. Endpoint DELETE untuk menghapus sensor
@app.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: int, db: Session = Depends(get_db)):
    db_sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if not db_sensor:
        raise HTTPException(status_code=404, detail="Sensor tidak ditemukan")
        
    db.delete(db_sensor)
    db.commit()
    
    # Hapus cache Redis
    redis_client.delete("all_sensors")
    
    return {"status": "sukses", "pesan": f"Sensor dengan ID {sensor_id} telah dihapus"}

@app.get("/readings", response_model=schemas.PaginatedReadings, status_code=200)
def get_paginated_readings(
    page: int = 1, 
    limit: int = 10, 
    db: Session = Depends(get_db)
):
    # Validasi input: Mencegah pengguna memasukkan halaman 0 atau angka negatif
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Parameter 'page' dan 'limit' harus bernilai 1 atau lebih besar.")

    # 1. Hitung total seluruh baris data yang ada di tabel readings
    total_data = db.query(models.Reading).count()

    # 2. Hitung berapa lompatan data (offset) yang harus dilakukan oleh database
    # Rumus: (Halaman - 1) * Batas Data Per Halaman
    # Contoh: Jika di halaman 2 dengan limit 10, maka lompat 10 data pertama, ambil data ke-11 dst.
    skip = (page - 1) * limit

    # 3. Eksekusi query dengan LIMIT dan OFFSET ke PostgreSQL
    readings = db.query(models.Reading).offset(skip).limit(limit).all()

    # 4. Hitung total halaman yang tersedia
    total_halaman = math.ceil(total_data / limit) if total_data > 0 else 1

    # 5. Kembalikan respons terstruktur sesuai standar RESTful API
    return {
        "total_data": total_data,
        "halaman_sekarang": page,
        "total_halaman": total_halaman,
        "data": readings
    }
    
@app.get("/secure-data")
def read_secure_data(token: str = Depends(oauth2_scheme)):
    # Jika token tidak disertakan atau tidak valid, FastAPI otomatis menolak akses
    return {"message": "Ini adalah data rahasia", "token_anda": token}

@app.post("/api/v1/sensors/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_sensor_data(
    payload: schemas.SensorDataIncoming,
    token: str = Depends(oauth2_scheme) 
):
    # Logika sementara: Mencatat penerimaan data di terminal.
    # Pada Fase 3, blok ini akan digantikan dengan perintah untuk 
    # mendelegasikan payload ke RabbitMQ/Celery secara asinkron.
    print(
        f"[{payload.timestamp}] Data dari {payload.device_id} | "
        f"Suhu: {payload.temperature}°C | Kelembapan: {payload.humidity}% | "
        f"Cahaya: {payload.light_intensity} lux | Status: {payload.sensor_status}"
    )
    
    # Merespons secepat mungkin dengan status 202 (Accepted) 
    # yang berarti permintaan telah diterima untuk diproses lebih lanjut.
    return {
        "status": "accepted",
        "message": "Payload berhasil diterima dan masuk antrean pemrosesan",
        "device_id": payload.device_id
    }