"""KarigarMitra stats server – counts businesses & quotations for the admin.
Run:  gunicorn -w 2 -b 127.0.0.1:5001 km_stats:app
Env:  KM_ADMIN_KEY (required, your secret)  KM_DB (sqlite path)  KM_ORIGINS (allowed site, e.g. https://karigarmitra.in)
"""
import os, json, sqlite3, hmac, datetime
from flask import Flask, request, jsonify

DB = os.environ.get("KM_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "km_stats.db"))
ADMIN_KEY = os.environ.get("KM_ADMIN_KEY", "")
ORIGINS = [o.strip() for o in os.environ.get("KM_ORIGINS", "*").split(",") if o.strip()]
app = Flask(__name__)

def db():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row; return c

with db() as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS shops(shop_id TEXT PRIMARY KEY, device TEXT, name TEXT, owner TEXT, phone TEXT,
      trades TEXT, address TEXT, lang TEXT, created TEXT, last TEXT);
    CREATE TABLE IF NOT EXISTS quotes(quote_id TEXT PRIMARY KEY, shop_id TEXT, total REAL, created TEXT, last TEXT);
    CREATE INDEX IF NOT EXISTS q_shop ON quotes(shop_id);
    """)

def cut(v, n=200): return str(v or "")[:n]
def now(): return datetime.datetime.utcnow().isoformat(timespec="seconds")

@app.after_request
def cors(r):
    o = request.headers.get("Origin", "")
    if "*" in ORIGINS: r.headers["Access-Control-Allow-Origin"] = "*"
    elif o in ORIGINS: r.headers["Access-Control-Allow-Origin"] = o; r.headers["Vary"] = "Origin"
    r.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return r

def body():
    try: return json.loads(request.get_data(as_text=True) or "{}")
    except Exception: return {}

@app.route("/api/km/events", methods=["POST", "OPTIONS"])
def events():
    if request.method == "OPTIONS": return ("", 204)
    evs = body().get("events", [])[:300]
    with db() as c:
        for e in evs:
            if not isinstance(e, dict): continue
            t, sid, at = e.get("type"), cut(e.get("shop_id"), 40), cut(e.get("at"), 30) or now()
            if not sid: continue
            if t in ("register", "update"):
                c.execute("""INSERT INTO shops(shop_id,device,name,owner,phone,trades,address,lang,created,last)
                  VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(shop_id) DO UPDATE SET name=excluded.name, owner=excluded.owner,
                  phone=excluded.phone, trades=excluded.trades, address=excluded.address, lang=excluded.lang, last=excluded.last""",
                  (sid, cut(e.get("device"), 40), cut(e.get("name")), cut(e.get("owner")), cut(e.get("phone"), 20),
                   cut(e.get("trades"), 300), cut(e.get("address"), 300), cut(e.get("lang"), 5), at, at))
            elif t == "quote" and e.get("quote_id"):
                c.execute("INSERT OR IGNORE INTO shops(shop_id,device,created,last) VALUES(?,?,?,?)", (sid, cut(e.get("device"), 40), at, at))
                c.execute("""INSERT INTO quotes(quote_id,shop_id,total,created,last) VALUES(?,?,?,?,?)
                  ON CONFLICT(quote_id) DO UPDATE SET total=excluded.total, last=excluded.last""",
                  (cut(e.get("quote_id"), 40), sid, float(e.get("total") or 0), at, at))
                c.execute("UPDATE shops SET last=? WHERE shop_id=? AND (last IS NULL OR last<?)", (at, sid, at))
    return jsonify(ok=True, n=len(evs))

@app.route("/api/km/stats", methods=["POST", "OPTIONS"])
def stats():
    if request.method == "OPTIONS": return ("", 204)
    if not ADMIN_KEY or not hmac.compare_digest(str(body().get("key", "")), ADMIN_KEY):
        return jsonify(error="unauthorized"), 401
    today = datetime.date.today().isoformat()
    with db() as c:
        rows = c.execute("""SELECT s.*, COUNT(q.quote_id) quotes, COALESCE(SUM(q.total),0) value
                            FROM shops s LEFT JOIN quotes q ON q.shop_id=s.shop_id GROUP BY s.shop_id
                            ORDER BY quotes DESC""").fetchall()
        tot_q = c.execute("SELECT COUNT(*) FROM quotes").fetchone()[0]
        tod_q = c.execute("SELECT COUNT(*) FROM quotes WHERE substr(created,1,10)=?", (today,)).fetchone()[0]
    biz = [dict(name=r["name"], owner=r["owner"], phone=r["phone"], trades=r["trades"], quotes=r["quotes"],
                value=r["value"], created=r["created"], last=r["last"]) for r in rows]
    return jsonify(totals=dict(businesses=len(biz), quotes=tot_q, today=tod_q), businesses=biz)

@app.route("/api/km/health")
def health(): return jsonify(ok=True)
