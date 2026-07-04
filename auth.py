from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt

# Pengaturan JWT
SECRET_KEY = "KUNCI_RAHASIA_SUPER_AMAN_UNTUK_GREENHOUSE" # Di produksi, gunakan env variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fungsi untuk mengubah password jadi hash biner terenkripsi
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Fungsi untuk mencocokkan password input dengan hash di database
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Fungsi untuk mencetak kartu token JWT
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt