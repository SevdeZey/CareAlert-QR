# app.py - Lokasyon yönetimi + Telegram bildirim + QR üretim destekli
import os
import sqlite3
import json
from datetime import datetime
import requests
import qrcode
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
    db.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT,
        type TEXT,
        qr_url TEXT,
        last_status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """)
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
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

@app.before_request
def before_request():
    if not hasattr(g, '_db_initialized'):
        init_db()
        g._db_initialized = True

# -----------------------
# Option lists (id + label)
# -----------------------
def options_for_type(typ):
    typ = (typ or "").lower()
    if typ in ("toilet", "tuvalet"):
        return [
            {"id":"dirty", "label":"Tuvalet genel temizliği gerekli"},
            {"id":"paper_out", "label":"Tuvalet kağıdı/peçete bitmiş"},
            {"id":"soap_out", "label":"Sıvı sabun tükenmiş"},
            {"id":"floor_wet", "label":"Zemin ıslak veya kaygan"},
            # opsiyonel öneriler:
            # {"id":"odor", "label":"Kötü koku / havalandırma problemi"},
            # {"id":"blockage", "label":"Klozet/tesisat tıkanması"}
        ]
    if typ in ("room", "oda"):
        return [
            {"id":"cleaning_needed", "label":"Oda temizliği gerekli"},
            {"id":"linen_change", "label":"Çarşaf / nevresim değişimi gerekli"},
            {"id":"room_vacated", "label":"Oda boşaldı (kontrol/temizlik gerekli)"},
            {"id":"trash_full", "label":"Çöp torbası dolu / boşaltılması gerekli"},
            {"id":"bathroom_issue", "label":"Oda içi lavabo/tuvalet ile ilgili sorun"},
            # opsiyonel:
            # {"id":"plumbing", "label":"Su/tesisat problemi"},
        ]
    return [{"id":"dirty", "label":"Genel temizlik gerekli"}]

# -----------------------
# QR üretim utility
# -----------------------
def create_qr_for_code(code):
    qr_dir = os.path.join(os.path.dirname(__file__), "static", "qrcodes")
    os.makedirs(qr_dir, exist_ok=True)
    url = f"{APP_URL}/feedback?loc={code}"
    img = qrcode.make(url)
    img_path = os.path.join(qr_dir, f"{code}.png")
    img.save(img_path)
    return img_path, url

# -----------------------
# Telegram gönderimi (opsiyonel)
# -----------------------
def send_telegram_message(text):
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if not token or not chat_id:
        # konfigurasyon yoksa sessizce atla
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": text})
        return resp.status_code == 200
    except Exception as e:
        print("Telegram gönderim hatası:", e)
        return False

# -----------------------
# Public: feedback page
# -----------------------
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

# -----------------------
# API: feedback al
# -----------------------
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

    # Telegram bildirimi (demo için)
    text = f"Yeni bildirim\n{loc['name']} ({loc['code']})\nDurum: {status_summary}\nNot: {note}"
    send_telegram_message(text)

    print(f"[NOTIFY] Lokasyon: {loc['name']} ({loc['code']}) - Durum: {status_summary} - Not: {note} - Zaman: {datetime.now()}")

    return jsonify({"ok": True})

# -----------------------
# Admin panel (giriş)
# -----------------------
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

# -----------------------
# Admin API: unresolved feedbacks
# -----------------------
@app.get("/api/unresolved")
def api_unresolved():
    rows = query_db("""
        SELECT f.id, f.status, f.meta, f.reported_at, f.resolved, l.code, l.name, l.type
        FROM feedbacks f
        JOIN locations l ON l.id = f.location_id
        WHERE f.resolved = 0
        ORDER BY f.reported_at DESC
        LIMIT 500
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
            "meta": meta
        })
    return jsonify(items)

# -----------------------
# Admin action: resolve feedback
# -----------------------
@app.post("/admin/resolve")
def admin_resolve():
    if not session.get("admin"):
        return jsonify({"error":"unauthorized"}), 401
    fid = request.form.get("feedback_id")
    if not fid:
        return jsonify({"error":"missing id"}), 400
    db = get_db()
    db.execute("UPDATE feedbacks SET resolved = 1 WHERE id = ?", (fid,))
    db.commit()
    return jsonify({"ok": True})

# -----------------------
# Admin: Lokasyon listeleme (JS ile çekeceğiz)
# -----------------------
@app.get("/api/locations")
def api_locations():
    rows = query_db("SELECT id, code, name, type, qr_url, last_status FROM locations ORDER BY id DESC")
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "type": r["type"],
            "qr_url": r["qr_url"],
            "last_status": r["last_status"]
        })
    return jsonify(out)

# -----------------------
# Admin: Lokasyon ekleme
# -----------------------
@app.post("/admin/locations/add")
def admin_locations_add():
    if not session.get("admin"):
        return jsonify({"error":"unauthorized"}), 401
    code = (request.form.get("code") or "").strip()
    name = (request.form.get("name") or "").strip()
    typ = (request.form.get("type") or "").strip()
    if not code or not name or not typ:
        return jsonify({"error":"Tüm alanları doldurun (code, name, type)"}), 400

    # duplicate kontrol
    existing = query_db("SELECT id FROM locations WHERE code = ?", [code], one=True)
    if existing:
        return jsonify({"error":"Aynı kod zaten var"}), 400

    qr_url = f"{APP_URL}/feedback?loc={code}"
    db = get_db()
    db.execute("INSERT INTO locations (code, name, type, qr_url, created_at) VALUES (?,?,?,?,datetime('now'))",
               (code, name, typ, qr_url))
    db.commit()

    # qr oluştur
    try:
        img_path, url = create_qr_for_code(code)
    except Exception as e:
        print("QR oluşturma hatası:", e)

    return jsonify({"ok": True, "qr_url": qr_url})

# -----------------------
# Admin: Lokasyon silme
# -----------------------
@app.post("/admin/locations/delete")
def admin_locations_delete():
    if not session.get("admin"):
        return jsonify({"error":"unauthorized"}), 401
    code = (request.form.get("code") or "").strip()
    if not code:
        return jsonify({"error":"Eksik parametre (code)"}), 400
    loc = query_db("SELECT id, qr_url FROM locations WHERE code = ?", [code], one=True)
    if not loc:
        return jsonify({"error":"Lokasyon bulunamadı"}), 404
    loc_id = loc["id"]
    db = get_db()
    # önce feedbackleri sil (basit)
    db.execute("DELETE FROM feedbacks WHERE location_id = ?", (loc_id,))
    db.execute("DELETE FROM locations WHERE id = ?", (loc_id,))
    db.commit()
    # qr dosyasını sil
    try:
        qr_path = os.path.join(os.path.dirname(__file__), "static", "qrcodes", f"{code}.png")
        if os.path.exists(qr_path):
            os.remove(qr_path)
    except Exception as e:
        print("QR silme hatası:", e)
    return jsonify({"ok": True})

# index yönlendirme
@app.get("/")
def index():
    return redirect(url_for("admin_index"))

if __name__ == "__main__":
    print("Sunucu başlatılıyor: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
