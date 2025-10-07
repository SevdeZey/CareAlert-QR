# migrate_users_schema.py
# Eksik users sütunlarını ekler ve eski 'password' sütununu password_hash'e çevirir.
import os, sqlite3, sys

DB = os.path.join(os.path.dirname(__file__), "data.db")

# Güvenli hash fonksiyonu: önce werkzeug deneyelim, yoksa basit hashlib fallback
try:
    from werkzeug.security import generate_password_hash
    HASH_LIB = "werkzeug"
except Exception:
    import hashlib
    def generate_password_hash(pw):
        # demo amaçlı saltlı sha256 (prod için werkzeug/pbkdf2 kullanın)
        return hashlib.sha256(("demo_salt_" + pw).encode("utf-8")).hexdigest()
    HASH_LIB = "hashlib_fallback"

def table_exists(conn, name):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def get_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def main():
    if not os.path.exists(DB):
        print("data.db bulunamadı. Lütfen uygulamayı veya init_db.py'yi çalıştırıp veritabanını oluşturun.")
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    if not table_exists(conn, "users"):
        print("users tablosu bulunamadı — yeni users tablosu oluşturuluyor...")
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("users tablosu oluşturuldu.")
    else:
        cols = get_columns(conn, "users")
        # password_hash ekle
        if "password_hash" not in cols:
            print("password_hash sütunu yok — ekleniyor...")
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            conn.commit()
            print("password_hash eklendi.")
        else:
            print("password_hash zaten var.")
        # is_admin ekle
        if "is_admin" not in cols:
            print("is_admin sütunu yok — ekleniyor...")
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            conn.commit()
            print("is_admin eklendi.")
        else:
            print("is_admin zaten var.")
        # created_at ekle
        if "created_at" not in cols:
            print("created_at sütunu yok — ekleniyor...")
            conn.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP")
            conn.commit()
            print("created_at eklendi.")
        else:
            print("created_at zaten var.")

    # Eğer eski migrationlarda 'password' veya 'role' gibi sütunlar varsa, migrate et
    cols = get_columns(conn, "users")
    if "password" in cols:
        print("Legacy 'password' sütunu bulundu. password_hash boş olanları migrate ediyorum...")
        rows = conn.execute("SELECT id, password FROM users WHERE password IS NOT NULL AND (password_hash IS NULL OR password_hash='')").fetchall()
        migrated = 0
        for r in rows:
            pw = r["password"]
            hashed = generate_password_hash(pw)
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, r["id"]))
            migrated += 1
        conn.commit()
        print(f"{migrated} satır migrate edildi (password -> password_hash) using {HASH_LIB}.")
    else:
        print("Legacy 'password' sütunu bulunmadı veya zaten migrate edilmiş.")

    # Eğer role sütunu varsa ve is_admin henüz set değilse dönüştür
    cols = get_columns(conn, "users")
    if "role" in cols:
        print("role sütunu bulundu. is_admin değerlerini role'a göre güncelliyorum...")
        rows = conn.execute("SELECT id, role FROM users WHERE role IS NOT NULL").fetchall()
        for r in rows:
            is_admin_val = 1 if str(r["role"]).lower() == "admin" else 0
            conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin_val, r["id"]))
        conn.commit()
        print("is_admin güncellendi.")
    else:
        print("role sütunu yok.")

    conn.close()
    print("Migration tamamlandı.")

if __name__ == '__main__':
    main()

