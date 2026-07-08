from celery import Celery
import time

celery_app = Celery(
    "greenhouse_worker",
    broker="amqp://guest:guest@rabbitmq:5672//",
    backend="redis://redis:6379/0"
)

@celery_app.task(name="process_sensor_data")
def process_sensor_data(payload_dict: dict):
    device_id = payload_dict.get('device_id')
    temp = payload_dict.get('temperature')
    hum = payload_dict.get('humidity')
    
    print(f"\n[Worker] Memulai evaluasi analitik untuk {device_id}...")
    
    # Waktu pemrosesan data (simulasi ekstraksi fitur)
    time.sleep(1.5)
    
    # --- Kerangka Evaluasi Prediktif ---
    # Di masa mendatang, blok if-else statis ini dapat langsung diganti
    # dengan skrip inferensi dari model Gradient Boosting pilihan Anda 
    # (seperti XGBoost, LightGBM, atau HistGradientBoosting) yang dimuat 
    # via joblib/pickle untuk mendeteksi anomali secara akurat.
    
    is_anomaly = False
    reasons = []
    
    # Simulasi logika deteksi batas ambang (threshold)
    if isinstance(temp, (int, float)):
        if temp > 35.0:
            is_anomaly = True
            reasons.append("Suhu terlampau tinggi (Overheat)")
        elif temp < 15.0:
            is_anomaly = True
            reasons.append("Suhu terlampau rendah")
            
    if isinstance(hum, (int, float)):
        if hum > 90.0 or hum < 40.0:
            is_anomaly = True
            reasons.append("Lonjakan/penurunan kelembapan tidak wajar")

    # Penentuan status akhir
    final_status = "CRITICAL_ANOMALY" if is_anomaly else "NORMAL"
    
    print(f"[Worker] Hasil Evaluasi {device_id}: {final_status}")
    if is_anomaly:
        print(f"[Worker] Peringatan Sistem: {', '.join(reasons)}")
        # Di skenario nyata, bagian ini akan memicu pengiriman email 
        # peringatan atau menyimpan status darurat ke database.
        
    return {
        "status": "evaluated",
        "device_id": device_id,
        "analysis_result": final_status,
        "details": reasons
    }