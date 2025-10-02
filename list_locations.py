# list_locations.py
import sqlite3
conn = sqlite3.connect("data.db")
cur = conn.cursor()
cur.execute("SELECT code, name, type FROM locations ORDER BY id")
rows = cur.fetchall()
if not rows:
    print("Veritabanında hiç lokasyon yok.")
else:
    for r in rows:
        print(r[0], "-", r[1], f"({r[2]})")
conn.close()
