from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import komponen dari aplikasi Anda
from main import app
from database import Base, get_db

# 1. Konfigurasi Database Pengujian (SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_database.db"

# SQLite memerlukan parameter check_same_thread=False
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Sinkronisasi skema tabel ke database pengujian
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# 3. Override dependensi database utama
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# 4. Inisialisasi Klien Pengujian
client = TestClient(app)

# 5. Skenario Pengujian Nyata
def test_register_user():
    """
    Menguji endpoint registrasi pengguna dengan simulasi HTTP POST
    """
    response = client.post(
        "/register",
        json={"username": "test_ci_user", "password": "securepassword"}
    )
    
    # Memastikan server merespons dengan kode 200 OK
    assert response.status_code == 201
    
    # Memastikan format data kembalian sesuai dengan skema
    data = response.json()
    assert data["pesan"] == "Akun berhasil dibuat"

def test_register_duplicate_user():
    """
    Menguji mekanisme proteksi duplikasi data
    """
    # Mencoba mendaftar dengan username yang sama dari pengujian pertama
    response = client.post(
        "/register",
        json={"username": "test_ci_user", "password": "anotherpassword"}
    )
    
    # Memastikan server menolak dengan kode 400 Bad Request
    assert response.status_code == 400
    assert response.json()["detail"] == "Username sudah terdaftar"