# migrate_add_floor.py
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "data.db")

def ensure_schema():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Var mı bak: locations tablosu
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locations'")
    if cur.fetchone() is None:
        print("locations tablosu bulunamadı — yeni tablolar oluşturuluyor.")
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT,
            type TEXT,
            qr_url TEXT,
            last_status TEXT,
            floor INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            status TEXT,
            meta TEXT,
            reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0,
            FOREIGN KEY(location_id) REFERENCES locations(id)
        );
        """)
        conn.commit()
        print("Yeni tablolar oluşturuldu.")
        conn.close()
        return

    # locations tablosu varsa sütunları kontrol et
    cur.execute("PRAGMA table_info(locations)")
    cols = [r[1] for r in cur.fetchall()]  # r[1] -> column name
    if "floor" in cols:
        print("Zaten 'floor' sütunu var, hiçbir değişiklik yapılmadı.")
        conn.close()
        return

    # Eğer yoksa ALTER TABLE ile ekle
    try:
        cur.execute("ALTER TABLE locations ADD COLUMN floor INTEGER")
        conn.commit()
        print("'floor' sütunu başarıyla eklendi.")
    except Exception as e:
        print("Sütun ekleme sırasında hata oldu:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    ensure_schema()
