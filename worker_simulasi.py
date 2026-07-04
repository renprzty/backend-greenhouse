import pika
import time
import json

# 1. Hubungkan ke RabbitMQ Server
credentials = pika.PlainCredentials('guest', 'guest')
connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq', credentials=credentials))
channel = connection.channel()

# 2. Buat antrean bernama 'tugas_ai_greenhouse'
channel.queue_declare(queue='tugas_ai_greenhouse', durable=True)

print(' [*] Worker siap menerima tugas analisis AI berat. Tekan CTRL+C untuk keluar.')

# 3. Fungsi yang akan berjalan saat ada antrean masuk
def callback(ch, method, properties, body):
    data = json.loads(body)
    print(f" [->] Menerima data sensor ID {data['sensor_id']} untuk dianalisis model AI...")
    
    # Simulasi proses komputasi berat (misal mendeteksi data spike selama 5 detik)
    time.sleep(5) 
    
    print(f" [V] Analisis Selesai! Hasil: Status Aman, Tidak Ada Anomali.")
    # Beri tahu RabbitMQ bahwa tugas sukses diselesaikan agar dihapus dari antrean
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Beritahu RabbitMQ agar memberikan 1 tugas saja per waktu ke worker ini
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='tugas_ai_greenhouse', on_message_callback=callback)

channel.start_consuming()