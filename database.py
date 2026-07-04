from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Format URL: postgresql://username:password@host:port/nama_database
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:rahasia@db:5432/postgres"

# Engine adalah mesin utama yang memegang koneksi ke database
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# SessionLocal digunakan untuk membuat sesi percakapan dengan database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base adalah cetakan dasar untuk membuat model tabel kita nanti
Base = declarative_base()

# Fungsi untuk membuka dan menutup koneksi database secara otomatis
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()