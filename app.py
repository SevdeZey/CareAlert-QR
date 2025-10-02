# app.py - GÜNCELLENMİŞ SÜRÜM (feedback checkbox + meta JSON desteği + bootstrap uyumlu)
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv

load_dotenv()

APP_URL = os.getenv("APP_URL", "http://localhost:5000")
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "secret")

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

# Ensure DB initialized on first request (Flask 3 compatibility)
@app.before_request
def before_request():
    if not hasattr(g, '_db_initialized'):
        init_db()
        g._db_initialized = True

# Yeni: location tipine göre checkbox seçenekleri döndüren yapı.
# Her öğe bir id (küçük, ASCII) ve bir label (gösterilecek, profesyonel metin) içerir.
def options_for_type(typ):
    typ = (typ or "").lower()
    if typ in ("toilet", "tuvalet"):
        return [
            {"id":"dirty", "label":"Tuvalet genel temizliği gerekli"},           # "Kirli"
            {"id":"paper_out", "label":"Tuvalet kağıdı bitmiş"},                # "Peçete bitmiş" daha profesyonel
            {"id":"soap_out", "label":"Sıvı sabun tükenmiş"},
            {"id":"floor_wet", "label":"Zemin ıslak / kaygan"},
            # Opsiyonel ekler (yorum): kötü koku, aydınlatma arızası, klozet tıkanması
            # {"id":"odor", "label":"Kötü koku / havalandırma problemi"},
            # {"id":"lighting", "label":"Aydınlatma arızası"},
            # {"id":"blockage", "label":"Klozet tıkanıklığı"}
        ]
    if typ in ("room", "oda"):
        return [
            {"id":"cleaning_needed", "label":"Oda temizliği gerekli"},
            {"id":"linen_change", "label":"Çarşaf / nevresim değişimi gerekli"},
            {"id":"room_vacated", "label":"Oda boşaldı (kontrol/temizlik gerekli)"},
            {"id":"trash_full", "label":"Çöp torbası dolu / boşaltılması gerekli"},
            {"id":"bathroom_issue", "label":"Oda içi lavabo/tuvalet ile ilgili problem"},
            # Opsiyonel ekler (yorum): elektrik/plumbing, yatak hasarı, hastanın eşyaları karışmış
            # {"id":"plumbing", "label":"Su/tesisat sorunu"},
            # {"id":"bed_damage", "label":"Yatak/koltuk/cihaz hasarı"}
        ]
    # default fallback (tuvalet tipinde varsayılan)
    return [
        {"id":"dirty", "label":"Genel temizlik gerekli"}
    ]

# Feedback sayfası (QR buraya yönlendirir)
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

# API: feedback al (hem checkbox listesi hem ek not kaydedilir)
@app.post("/api/feedback")
def api_feedback():
    data = request.get_json() or request.form
    code = data.get("location_code") or data.get("loc") or data.get("location")
    # "issues" bekliyoruz: liste halinde checkbox id'leri
    issues = data.get("issues") or []
    # eğer issues tekil string gelirse (form-style) onu liste yap
    if isinstance(issues, str):
        # beklenen format JSON string veya tek değer; deneme yap
        try:
            parsed = json.loads(issues)
            if isinstance(parsed, list):
                issues = parsed
            else:
                issues = [str(parsed)]
        except Exception:
            issues = [issues]
    note = data.get("note") or ""

    if not code or (not issues and not note):
        # en az bir sorun seçilmeli veya not girilmeli
        return jsonify({"error":"Eksik alan (en az bir seçenek seçilmeli veya not girilmeli)"}), 400

    loc = query_db("SELECT * FROM locations WHERE code = ?", [code], one=True)
    if not loc:
        return jsonify({"error":"Konum bulunamadı"}), 400

    # map id -> label (kullanıcı okumayı kolaylaştırmak için)
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

    # Demo: konsola anlık bildirim yaz (prod: SMS/WhatsApp/Push entegrasyonu burada olur)
    print(f"[NOTIFY] Lokasyon: {loc['name']} ({loc['code']}) - Durum: {status_summary} - Not: {note} - Zaman: {datetime.now()}")

    return jsonify({"ok": True})

# Admin login / panel
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

# Admin API: çözülmemiş feedback'leri JSON ile ver (meta'yı parse et)
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

# Admin action: resolve feedback
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

# index -> admin yönlendirme (kullanışlı)
@app.get("/")
def index():
    return redirect(url_for("admin_index"))

if __name__ == "__main__":
    print("Sunucu başlatılıyor: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)














# ********** ONCCEKI KODLAR: **********

# # app.py
# import os
# import sqlite3
# import json
# from datetime import datetime
# from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify
# from dotenv import load_dotenv

# load_dotenv()

# APP_URL = os.getenv("APP_URL", "http://localhost:5000")
# DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
# ADMIN_USER = os.getenv("ADMIN_USER", "admin")
# ADMIN_PASS = os.getenv("ADMIN_PASS", "secret")

# app = Flask(__name__, static_folder="static", template_folder="templates")
# app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-it")

# def get_db():
#     db = getattr(g, "_database", None)
#     if db is None:
#         db = g._database = sqlite3.connect(DB_PATH)
#         db.row_factory = sqlite3.Row
#     return db

# def query_db(query, args=(), one=False):
#     cur = get_db().execute(query, args)
#     rv = cur.fetchall()
#     cur.close()
#     return (rv[0] if rv else None) if one else rv

# def init_db():
#     db = get_db()
#     db.execute("""
#     CREATE TABLE IF NOT EXISTS locations (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         code TEXT UNIQUE,
#         name TEXT,
#         type TEXT,
#         qr_url TEXT,
#         last_status TEXT,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         updated_at TIMESTAMP
#     );
#     """)
#     db.execute("""
#     CREATE TABLE IF NOT EXISTS feedbacks (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         location_id INTEGER,
#         status TEXT,
#         meta TEXT,
#         reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         resolved INTEGER DEFAULT 0,
#         FOREIGN KEY(location_id) REFERENCES locations(id)
#     );
#     """)
#     db.commit()

# @app.teardown_appcontext
# def close_connection(exception):
#     db = getattr(g, "_database", None)
#     if db is not None:
#         db.close()

# # @app.before_first_request
# # def startup():
# #     init_db()

# @app.before_request
# def before_request():
#     if not hasattr(g, '_db_initialized'):
#         init_db()  
#         g._db_initialized = True



# # Helper: get options by location type
# def options_for_type(typ):
#     typ = (typ or "").lower()
#     if typ == "toilet" or typ == "tuvalet":
#         return ["Kirli"]
#     if typ == "room" or typ == "oda":
#         return ["Kirli", "Boşaldı"]
#     # default
#     return ["Kirli"]

# # Public feedback page (QR leads here)
# @app.get("/feedback")
# def feedback_page():
#     code = request.args.get("loc")
#     if not code:
#         return "Eksik parametre. (loc gerekli)", 400
#     loc = query_db("SELECT * FROM locations WHERE code = ?", [code], one=True)
#     if not loc:
#         return "Konum bulunamadı.", 404
#     opts = options_for_type(loc["type"])
#     return render_template("feedback.html", location=loc, options=opts)

# # API to receive feedback (AJAX call from feedback page)
# @app.post("/api/feedback")
# def api_feedback():
#     data = request.get_json() or request.form
#     code = data.get("location_code") or data.get("loc") or data.get("location")
#     status = data.get("status")
#     if not code or not status:
#         return jsonify({"error":"Eksik alan"}), 400
#     loc = query_db("SELECT * FROM locations WHERE code = ?", [code], one=True)
#     if not loc:
#         return jsonify({"error":"Konum bulunamadı"}), 400
#     db = get_db()
#     db.execute("INSERT INTO feedbacks (location_id, status, meta, reported_at) VALUES (?,?,?,datetime('now'))",
#                (loc["id"], status, json.dumps({})))
#     db.execute("UPDATE locations SET last_status=?, updated_at=datetime('now') WHERE id=?", (status, loc["id"]))
#     db.commit()

#     # Demo için anlık bildirim console'a yazıyoruz (prod'da SMS/Push/WhatsApp vb. gönderilecek)
#     print(f"[NOTIFY] Lokasyon: {loc['name']} ({loc['code']}) - Durum: {status} - Zaman: {datetime.now()}")

#     return jsonify({"ok":True})

# # Admin login page
# @app.get("/admin")
# def admin_index():
#     if not session.get("admin"):
#         return render_template("login.html")
#     return render_template("admin.html")

# @app.post("/admin/login")
# def admin_login():
#     username = request.form.get("username")
#     password = request.form.get("password")
#     if username == ADMIN_USER and password == ADMIN_PASS:
#         session["admin"] = True
#         return redirect(url_for("admin_index"))
#     return render_template("login.html", error="Kullanıcı/şifre hatalı")

# @app.post("/admin/logout")
# def admin_logout():
#     session.pop("admin", None)
#     return redirect(url_for("admin_index"))

# # API for admin polling: unresolved feedbacks
# @app.get("/api/unresolved")
# def api_unresolved():
#     rows = query_db("""
#         SELECT f.id, f.status, f.reported_at, f.resolved, l.code, l.name, l.type
#         FROM feedbacks f
#         JOIN locations l ON l.id = f.location_id
#         WHERE f.resolved = 0
#         ORDER BY f.reported_at DESC
#         LIMIT 200
#     """)
#     items = []
#     for r in rows:
#         items.append({
#             "id": r["id"],
#             "status": r["status"],
#             "reported_at": r["reported_at"],
#             "code": r["code"],
#             "name": r["name"],
#             "type": r["type"]
#         })
#     return jsonify(items)

# # Admin action: resolve feedback
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

# if __name__ == "__main__":
#     print("Sunucu başlatılıyor: http://localhost:5000")
#     app.run(host="0.0.0.0", port=5000, debug=True)

# @app.get("/")
# def index():
#     return redirect(url_for("admin_index"))


