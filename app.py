# app.py - PERSONEL / KAT SORUMLULUĞU DİZİLİMİ EKLENMİŞ SÜRÜM
import os
import sqlite3
import json
from datetime import datetime
import requests
import qrcode
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv

load_dotenv()

APP_URL = os.getenv("APP_URL", "http://localhost:5000")
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "secret")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-it")

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    db = get_db()
    # locations (floor column dahil)
    db.execute("""
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
    """)
    # feedbacks
    db.execute("""
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
    # users (personel)
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # user_floors mapping
    db.execute("""
    CREATE TABLE IF NOT EXISTS user_floors (
        user_id INTEGER,
        floor INTEGER,
        UNIQUE(user_id, floor)
    );
    """)
    db.commit()
    # migration safety: if older locations table lacked 'floor', try add (sqlite allows ADD COLUMN)
    try:
        db.execute("ALTER TABLE locations ADD COLUMN floor INTEGER")
        db.commit()
    except Exception:
        # column varsa veya başka hata varsa atla
        pass

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# helper: options
def options_for_type(typ):
    typ = (typ or "").lower()
    if typ in ("toilet", "tuvalet"):
        return [
            {"id":"dirty", "label":"Tuvalet genel temizliği gerekli"},
            {"id":"paper_out", "label":"Tuvalet kâğıdı/peçete bitmiş"},
            {"id":"soap_out", "label":"Sıvı sabun tükenmiş"},
            {"id":"floor_wet", "label":"Zemin ıslak / kaygan"},
        ]
    if typ in ("room", "oda"):
        return [
            {"id":"cleaning_needed", "label":"Oda temizliği gerekli"},
            {"id":"linen_change", "label":"Çarşaf / nevresim değişimi gerekli"},
            {"id":"room_vacated", "label":"Oda boşaldı (kontrol/temizlik gerekli)"},
            {"id":"trash_full", "label":"Çöp torbası dolu / boşaltılması gerekli"},
        ]
    return [{"id":"dirty", "label":"Genel temizlik gerekli"}]

# QR utility
def create_qr_for_code(code):
    qr_dir = os.path.join(os.path.dirname(__file__), "static", "qrcodes")
    os.makedirs(qr_dir, exist_ok=True)
    url = f"{APP_URL}/feedback?loc={code}"
    img = qrcode.make(url)
    img_path = os.path.join(qr_dir, f"{code}.png")
    img.save(img_path)
    return img_path, url

# telegram send
def send_telegram_message(text):
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": text})
        return resp.status_code == 200
    except Exception as e:
        print("Telegram error:", e)
        return False

# PUBLIC: feedback page
@app.get("/feedback")
def feedback_page():
    code = request.args.get("loc")
    if not code:
        return "Eksik parametre. (loc gerekli)", 400
    loc = query_db("SELECT * FROM locations WHERE code = ?", [code], one=True)
    if not loc:
        return "Konum bulunamadı.", 404
    opts = options_for_type(loc["type"])
    return render_template("feedback.html", location=loc, options=opts)

# PUBLIC API: feedback al
@app.post("/api/feedback")
def api_feedback():
    data = request.get_json() or request.form
    code = data.get("location_code") or data.get("loc") or data.get("location")
    issues = data.get("issues") or []
    if isinstance(issues, str):
        try:
            parsed = json.loads(issues)
            if isinstance(parsed, list):
                issues = parsed
            else:
                issues = [issues]
        except Exception:
            issues = [issues]
    note = data.get("note") or ""
    if not code or (not issues and not note):
        return jsonify({"error":"Eksik alan (en az bir seçenek seçilmeli veya not girilmeli)"}), 400
    loc = query_db("SELECT * FROM locations WHERE code = ?", [code], one=True)
    if not loc:
        return jsonify({"error":"Konum bulunamadı"}), 400
    mapping = {opt["id"]: opt["label"] for opt in options_for_type(loc["type"])}
    issues_with_label = []
    for i in issues:
        issues_with_label.append({"id": i, "label": mapping.get(i, i)})
    status_summary = ", ".join([it["label"] for it in issues_with_label]) if issues_with_label else (note[:100] or "Bildirim")
    meta_obj = {
        "issues": issues_with_label,
        "note": note,
        "reported_at": datetime.utcnow().isoformat() + "Z"
    }
    db = get_db()
    db.execute("INSERT INTO feedbacks (location_id, status, meta, reported_at) VALUES (?,?,?,datetime('now'))",
               (loc["id"], status_summary, json.dumps(meta_obj, ensure_ascii=False)))
    db.execute("UPDATE locations SET last_status=?, updated_at=datetime('now') WHERE id=?", (status_summary, loc["id"]))
    db.commit()
    # Telegram (demo): admin chat receives all messages (per-personalization later)
    text = f"Yeni bildirim\n{loc['name']} ({loc['code']})\nDurum: {status_summary}\nNot: {note}"
    send_telegram_message(text)
    print(f"[NOTIFY] Lokasyon: {loc['name']} ({loc['code']}) - Durum: {status_summary} - Not: {note} - Zaman: {datetime.now()}")
    return jsonify({"ok": True})

# ADMIN: login & panel
@app.get("/admin")
def admin_index():
    if not session.get("admin"):
        return render_template("login.html")
    return render_template("admin.html")

@app.post("/admin/login")
def admin_login():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == ADMIN_USER and password == ADMIN_PASS:
        session["admin"] = True
        return redirect(url_for("admin_index"))
    return render_template("login.html", error="Kullanıcı/şifre hatalı")

@app.post("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_index"))

# admin_resolve: hem admin hem staff için çalışır; staff sadece kendi katları için silme yapabilir
@app.post("/admin/resolve")
def admin_resolve():
    fid = request.form.get("feedback_id") or (request.get_json() or {}).get("feedback_id")
    if not fid:
        return jsonify({"error":"missing id"}), 400

    db = get_db()

    # feedback ve onun lokasyon bilgisini al
    row = query_db("""
        SELECT f.id AS fid, f.location_id, l.floor
        FROM feedbacks f
        JOIN locations l ON l.id = f.location_id
        WHERE f.id = ?
    """, (fid,), one=True)

    if not row:
        return jsonify({"error":"not found"}), 404

    # yetki kontrolü: admin ise her yerden silebilir
    if session.get("admin"):
        allowed = True
    else:
        # staff ise sadece kendisine atanan katlar için izin ver
        sid = session.get("staff_id")
        if not sid:
            return jsonify({"error":"unauthorized"}), 401
        floors = [r["floor"] for r in query_db("SELECT floor FROM user_floors WHERE user_id = ?", [sid])]
        if not floors:
            return jsonify({"error":"forbidden - no floors assigned"}), 403
        allowed = (row["floor"] in floors)

    if not allowed:
        return jsonify({"error":"forbidden"}), 403

    # İSTEM: silmek istiyoruz (anında)
    try:
        db.execute("DELETE FROM feedbacks WHERE id = ?", (fid,))
        db.commit()
    except Exception as e:
        return jsonify({"error":"db error: "+str(e)}), 500

    # başarılı
    return jsonify({"ok": True})


# @app.post("/admin/resolve")
# def admin_resolve():
#     if not session.get("admin"):
#         return jsonify({"error":"unauthorized"}), 401
#     fid = request.form.get("feedback_id")
#     if not fid:
#         return jsonify({"error":"missing id"}), 400
#     db = get_db()
#     db.execute("UPDATE feedbacks SET resolved = 1 WHERE id = ?", (fid,))
#     db.commit()
#     return jsonify({"ok": True})


# ADMIN API: unresolved (admin sees all)
@app.get("/api/unresolved")
def api_unresolved():
    rows = query_db("""
        SELECT f.id, f.status, f.meta, f.reported_at, f.resolved, l.code, l.name, l.type, l.floor
        FROM feedbacks f
        JOIN locations l ON l.id = f.location_id
        WHERE f.resolved = 0
        ORDER BY f.reported_at DESC
        LIMIT 1000
    """)
    items = []
    for r in rows:
        try:
            meta = json.loads(r["meta"]) if r["meta"] else {}
        except Exception:
            meta = {"raw": r["meta"]}
        items.append({
            "id": r["id"],
            "status": r["status"],
            "reported_at": r["reported_at"],
            "code": r["code"],
            "name": r["name"],
            "type": r["type"],
            "floor": r["floor"],
            "meta": meta
        })
    return jsonify(items)

# ADMIN: staff add (only admin)
@app.post("/admin/staff/add")
def admin_staff_add():
    if not session.get("admin"):
        return jsonify({"error":"unauthorized"}), 401
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    floors = request.form.getlist("floors")
    if not username or not password:
        return jsonify({"error":"Kullanıcı adı ve şifre gerekli"}), 400
    hashed = generate_password_hash(password)
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?,?,0)", (username, hashed))
        db.commit()
        user = query_db("SELECT id FROM users WHERE username = ?", [username], one=True)
        uid = user["id"]
        # insert floors
        for f in floors:
            try:
                fi = int(f)
                db.execute("INSERT OR IGNORE INTO user_floors (user_id, floor) VALUES (?,?)", (uid, fi))
            except:
                pass
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error":"Kullanıcı oluşturulamadı: "+str(e)}), 400

# ADMIN: staff delete
@app.post("/admin/staff/delete")
def admin_staff_delete():
    if not session.get("admin"):
        return jsonify({"error":"unauthorized"}), 401
    username = (request.form.get("username") or "").strip()
    if not username:
        return jsonify({"error":"username required"}), 400
    db = get_db()
    user = query_db("SELECT id FROM users WHERE username = ?", [username], one=True)
    if not user:
        return jsonify({"error":"Kullanıcı bulunamadı"}), 404
    uid = user["id"]
    db.execute("DELETE FROM user_floors WHERE user_id = ?", (uid,))
    db.execute("DELETE FROM users WHERE id = ?", (uid,))
    db.commit()
    return jsonify({"ok": True})

# ADMIN: list staff
@app.get("/api/staff")
def api_staff():
    # admin-only
    if not session.get("admin"):
        return jsonify({"error":"unauthorized"}), 401
    rows = query_db("SELECT id, username, is_admin, created_at FROM users ORDER BY id DESC")
    out = []
    for r in rows:
        floors = query_db("SELECT floor FROM user_floors WHERE user_id = ?", [r["id"]])
        floor_list = [fr["floor"] for fr in floors]
        out.append({"id": r["id"], "username": r["username"], "is_admin": r["is_admin"], "floors": floor_list})
    return jsonify(out)

# STAFF: login
@app.get("/staff/login")
def staff_login_page():
    return render_template("staff_login.html")

@app.post("/staff/login")
def staff_login():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    user = query_db("SELECT id, username, password_hash, is_admin FROM users WHERE username = ?", [username], one=True)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("staff_login.html", error="Kullanıcı/şifre hatalı")
    session["staff_id"] = user["id"]
    return redirect(url_for("staff_dashboard"))

@app.post("/staff/logout")
def staff_logout():
    session.pop("staff_id", None)
    return redirect(url_for("staff_login_page"))

# STAFF: dashboard
@app.get("/staff")
def staff_dashboard():
    if not session.get("staff_id"):
        return redirect(url_for("staff_login_page"))
    return render_template("staff_dashboard.html")

# STAFF API: unresolved for their floors
@app.get("/staff/api/unresolved")
def staff_api_unresolved():
    sid = session.get("staff_id")
    if not sid:
        return jsonify({"error":"unauthorized"}), 401
    floors = query_db("SELECT floor FROM user_floors WHERE user_id = ?", [sid])
    floor_list = [f["floor"] for f in floors]
    if not floor_list:
        return jsonify([])
    placeholders = ",".join(["?"]*len(floor_list))
    sql = f"""
        SELECT f.id, f.status, f.meta, f.reported_at, f.resolved, l.code, l.name, l.type, l.floor
        FROM feedbacks f
        JOIN locations l ON l.id = f.location_id
        WHERE f.resolved = 0 AND l.floor IN ({placeholders})
        ORDER BY f.reported_at DESC
        LIMIT 1000
    """
    rows = query_db(sql, floor_list)
    items = []
    for r in rows:
        try:
            meta = json.loads(r["meta"]) if r["meta"] else {}
        except Exception:
            meta = {"raw": r["meta"]}
        items.append({
            "id": r["id"],
            "status": r["status"],
            "reported_at": r["reported_at"],
            "code": r["code"],
            "name": r["name"],
            "type": r["type"],
            "floor": r["floor"],
            "meta": meta
        })
    return jsonify(items)

# admin index redirect
@app.get("/")
def index():
    return redirect(url_for("admin_index"))

if __name__ == "__main__":
    print("Sunucu başlatılıyor: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
