# db_init.py
# Güvenli şekilde mevcut data.db'yi yedekler ve yeni, doğru şemayla data.db oluşturur.
import os, sqlite3, shutil, datetime
DB = os.path.join(os.path.dirname(__file__), "data.db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

# hash fonksiyonu
try:
    from werkzeug.security import generate_password_hash
except Exception:
    import hashlib
    def generate_password_hash(pw):
        return hashlib.sha256(("demo_salt_" + pw).encode("utf-8")).hexdigest()

def backup_existing_db():
    if os.path.exists(DB):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(BACKUP_DIR, f"data.db.bak.{ts}")
        shutil.move(DB, dest)
        print(f"Mevcut data.db yedeklendi -> {dest}")
    else:
        print("Mevcut data.db bulunmuyor. Yeni veritabanı oluşturulacak.")

def create_schema_and_seed():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.executescript("""
    PRAGMA foreign_keys = ON;

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

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_floors (
        user_id INTEGER,
        floor INTEGER,
        UNIQUE(user_id, floor),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()

    # örnek staff (temizlik personeli) ekle (test amaçlı)
    try:
        pw_hash = generate_password_hash("pass1")
        cur.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)", ("temizlik1", pw_hash))
        conn.commit()
        uid = cur.lastrowid
        # örnek: temizlik1 -> 1,2,3 katları
        cur.executemany("INSERT OR IGNORE INTO user_floors (user_id, floor) VALUES (?, ?)", [(uid,1),(uid,2),(uid,3)])
        conn.commit()
        print("Örnek kullanıcı 'temizlik1' oluşturuldu (parola: pass1) ve 1,2,3 katları atandı.")
    except Exception as e:
        print("Örnek kullanıcı eklenemedi (muhtemelen zaten var):", e)

    conn.close()
    print("Yeni veritabanı şeması oluşturuldu.")

if __name__ == "__main__":
    backup_existing_db()
    create_schema_and_seed()
    print("db_init.py tamamlandı. (data.db hazır)")
