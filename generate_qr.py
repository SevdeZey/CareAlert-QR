# generate_qr.py
import os, sqlite3
import qrcode

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
APP_URL = os.getenv("APP_URL", "http://localhost:5000")
QRC_DIR = os.path.join(os.path.dirname(__file__), "static", "qrcodes")

os.makedirs(QRC_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# create tables if not exist (same as app)
c.execute("""CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT,
    type TEXT,
    qr_url TEXT,
    last_status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);""")
conn.commit()

# örnek lokasyonlar (dilersen bu listeyi değiştir)
locations = [
    ("L0001", "Zemin Kat Bayan WC", "toilet"),
    ("L0002", "Zemin Kat Erkek WC", "toilet"),
    ("R1001", "2. Kat - Oda 201 - Yatak 1", "room"),
    ("R1002", "2. Kat - Oda 201 - Yatak 2", "room"),
]

for code, name, typ in locations:
    # insert if not exists
    c.execute("SELECT id FROM locations WHERE code = ?", (code,))
    if c.fetchone() is None:
        qr_url = f"{APP_URL}/feedback?loc={code}"
        c.execute("INSERT INTO locations (code, name, type, qr_url) VALUES (?,?,?,?)",
                  (code, name, typ, qr_url))
        conn.commit()
    else:
        # update qr_url if needed
        qr_url = f"{APP_URL}/feedback?loc={code}"
        c.execute("UPDATE locations SET qr_url = ? WHERE code = ?", (qr_url, code))
        conn.commit()

    # create QR image
    img = qrcode.make(f"{APP_URL}/feedback?loc={code}")
    img_path = os.path.join(QRC_DIR, f"{code}.png")
    img.save(img_path)
    print("QR oluşturuldu:", img_path)

conn.close()
print("Tamam. Lokasyonlar veritabanına eklendi ve QR'lar oluşturuldu.")
