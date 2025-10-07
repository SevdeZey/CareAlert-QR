# init_db.py
import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

# Kullanıcı tablosu (admin + personel)
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','staff')),
    floors TEXT
)
""")

# Lokasyon tablosu (QR kodla eşleşecek odalar/alanlar)
cur.execute("""
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT
)
""")

# Bildirim tablosu (hangi lokasyondan hangi temizlik bildirimi gelmiş)
cur.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    staff_id INTEGER,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(location_id) REFERENCES locations(id),
    FOREIGN KEY(staff_id) REFERENCES users(id)
)
""")

# İlk admin kullanıcısını ekleyelim (username=admin, password=secret)
try:
    cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", "secret", "admin"))
    print("Admin kullanıcı oluşturuldu.")
except sqlite3.IntegrityError:
    print("Admin zaten var, yeniden oluşturulmadı.")

conn.commit()
conn.close()
print("Veritabanı tabloları hazır.")
