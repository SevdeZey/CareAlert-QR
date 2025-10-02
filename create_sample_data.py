# create_sample_data.py - 10 kat x 3 lokasyon (örnek)
import os, sqlite3
import qrcode

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
QR_DIR = os.path.join(os.path.dirname(__file__), "static", "qrcodes")
os.makedirs(QR_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

for floor in range(1, 11):  # 1..10
    code_w = f"F{floor:02d}-W"
    name_w = f"{floor}. Kat - Bayan WC"
    code_m = f"F{floor:02d}-M"
    name_m = f"{floor}. Kat - Erkek WC"
    code_r = f"F{floor:02d}-R"
    name_r = f"{floor}. Kat - Yataklı Oda"

    for code, name, typ in [(code_w, name_w, "toilet"), (code_m, name_m, "toilet"), (code_r, name_r, "room")]:
        cur.execute("SELECT id FROM locations WHERE code = ?", (code,))
        if cur.fetchone() is None:
            qr_url = f"http://localhost:5000/feedback?loc={code}"
            cur.execute("INSERT INTO locations (code, name, type, qr_url, floor, created_at) VALUES (?,?,?,?,?,datetime('now'))",
                        (code, name, typ, qr_url, floor))
            conn.commit()
        # create qr
        img = qrcode.make(f"http://localhost:5000/feedback?loc={code}")
        img_path = os.path.join(QR_DIR, f"{code}.png")
        img.save(img_path)
        print("Created:", code, img_path)

conn.close()
print("Örnek lokasyonlar oluşturuldu.")
