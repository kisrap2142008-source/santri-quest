from flask import Flask, jsonify, request, render_template
import sqlite3
import os
from datetime import date, datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "database.db")

EXP_TABLE = {
    1:100,  2:200,  3:350,  4:500,  5:700,
    6:900,  7:1150, 8:1400, 9:1700, 10:2000,
    11:2400,12:2800,13:3300,14:3800,15:4500,
    16:5200,17:6000,18:7000,19:8000,20:9999999
}

STATUS_TABLE = {
    1:"Santri Baru", 5:"Santri Aktif", 10:"Santri Disiplin",
    15:"Santri Produktif", 20:"Santri Teladan"
}

# Quest harian + deadline jam + penalty EXP jika gagal
DAILY_QUESTS = [
    # (title, description, exp_reward, agama, it, disiplin, akhlak, deadline_jam, exp_penalty_gagal)
    ("Mengaji 30 Menit",   "Baca Al-Qur'an minimal 30 menit",          40, 1, 0, 0, 1, "08:00", 20),
    ("Sholat Tepat Waktu", "Sholat 5 waktu tepat waktu & berjamaah",   50, 1, 0, 1, 1, "21:00", 25),
    ("Belajar IT",         "Pelajari materi IT / coding minimal 1 jam", 40, 0, 1, 0, 0, "20:00", 15),
    ("Membaca Buku",       "Baca buku pengetahuan minimal 20 halaman",  30, 1, 0, 0, 0, "21:00", 10),
    ("Olahraga",           "Olahraga pagi/sore minimal 20 menit",       25, 0, 0, 1, 0, "17:00", 10),
    ("Membersihkan Kamar", "Bersihkan dan rapikan kamar tidur",         20, 0, 0, 1, 1, "09:00", 10),
    ("Membantu Teman",     "Bantu teman yang kesulitan dengan ikhlas",  30, 0, 0, 0, 2, "22:00",  5),
]

def get_status(level):
    status = "Santri Baru"
    for lvl, s in STATUS_TABLE.items():
        if level >= lvl:
            status = s
    return status

def exp_needed(level):
    return EXP_TABLE.get(level, 9999999)

def today():
    return date.today().strftime("%Y-%m-%d")

def now_time():
    return datetime.now().strftime("%H:%M")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS player (
        id       INTEGER PRIMARY KEY,
        name     TEXT    NOT NULL,
        level    INTEGER DEFAULT 1,
        exp      INTEGER DEFAULT 0,
        agama    INTEGER DEFAULT 0,
        it_skill INTEGER DEFAULT 0,
        disiplin INTEGER DEFAULT 0,
        akhlak   INTEGER DEFAULT 0,
        status   TEXT    DEFAULT "Santri Baru"
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS quest (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        title           TEXT    NOT NULL,
        description     TEXT,
        exp_reward      INTEGER DEFAULT 0,
        agama_reward    INTEGER DEFAULT 0,
        it_reward       INTEGER DEFAULT 0,
        disiplin_reward INTEGER DEFAULT 0,
        akhlak_reward   INTEGER DEFAULT 0,
        completed       INTEGER DEFAULT 0,
        quest_date      TEXT    DEFAULT "1970-01-01",
        deadline        TEXT    DEFAULT "23:59",
        exp_penalty     INTEGER DEFAULT 0,
        failed          INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS violation (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        title          TEXT    NOT NULL,
        exp_penalty    INTEGER DEFAULT 0,
        violation_date TEXT    DEFAULT "1970-01-01"
    )''')

    c.execute("SELECT COUNT(*) FROM player")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO player (id,name,level,exp,agama,it_skill,disiplin,akhlak,status) VALUES (1,'Hunter',1,0,0,0,0,0,'Santri Baru')")

    conn.commit()
    conn.close()
    seed_quests()

def seed_quests():
    tgl = today()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM quest WHERE quest_date=?", (tgl,))
    if c.fetchone()[0] == 0:
        for q in DAILY_QUESTS:
            c.execute(
                "INSERT INTO quest (title,description,exp_reward,agama_reward,it_reward,disiplin_reward,akhlak_reward,quest_date,deadline,exp_penalty) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (q[0], q[1], q[2], q[3], q[4], q[5], q[6], tgl, q[7], q[8])
            )
        conn.commit()
        print(f"[OK] Quest harian dibuat untuk {tgl}")
    conn.close()

def check_expired_quests():
    """Cek quest yang sudah lewat deadline dan belum selesai → tandai failed + kurangi EXP"""
    tgl  = today()
    now  = now_time()
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # Ambil quest yang belum selesai, belum failed, dan sudah lewat deadline
    c.execute("""SELECT id, exp_penalty FROM quest
                 WHERE quest_date=? AND completed=0 AND failed=0 AND deadline < ?""",
              (tgl, now))
    expired = c.fetchall()

    failed_list = []
    for qid, penalty in expired:
        # Tandai failed
        c.execute("UPDATE quest SET failed=1 WHERE id=?", (qid,))
        # Kurangi EXP player
        c.execute("SELECT exp FROM player WHERE id=1")
        exp = c.fetchone()[0]
        new_exp = max(0, exp - penalty)
        c.execute("UPDATE player SET exp=? WHERE id=1", (new_exp,))
        failed_list.append({"id": qid, "exp_lost": penalty})

    if expired:
        conn.commit()
    conn.close()
    return failed_list

# ── ROUTES ────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/player")
def get_player():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM player WHERE id=1")
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Player not found"}), 404
    return jsonify({
        "id": row[0], "name": row[1], "level": row[2], "exp": row[3],
        "agama": row[4], "it_skill": row[5], "disiplin": row[6],
        "akhlak": row[7], "status": row[8],
        "exp_needed": exp_needed(row[2])
    })

@app.route("/api/player/name", methods=["POST"])
def update_name():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama kosong"}), 400
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE player SET name=? WHERE id=1", (name,))
    conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route("/api/quests")
def get_quests():
    seed_quests()
    failed = check_expired_quests()  # cek expired setiap kali load
    tgl  = today()
    now  = now_time()
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT * FROM quest WHERE quest_date=? ORDER BY deadline", (tgl,))
    rows = c.fetchall()
    conn.close()
    return jsonify({
        "quests": [{
            "id": r[0], "title": r[1], "description": r[2],
            "exp_reward": r[3], "agama_reward": r[4], "it_reward": r[5],
            "disiplin_reward": r[6], "akhlak_reward": r[7],
            "completed": bool(r[8]),
            "deadline": r[10],
            "exp_penalty": r[11],
            "failed": bool(r[12]),
            "expired": (now > r[10] and not bool(r[8]) and not bool(r[12]))
        } for r in rows],
        "newly_failed": failed,
        "current_time": now
    })

@app.route("/api/quest/complete/<int:qid>", methods=["POST"])
def complete_quest(qid):
    tgl = today()
    now = now_time()
    conn = sqlite3.connect(DB_PATH)
    c   = conn.cursor()

    c.execute("SELECT * FROM quest WHERE id=? AND quest_date=?", (qid, tgl))
    quest = c.fetchone()
    if not quest:
        conn.close(); return jsonify({"error": "Quest tidak ditemukan"}), 404
    if quest[8]:
        conn.close(); return jsonify({"error": "Quest sudah selesai"}), 400
    if quest[12]:
        conn.close(); return jsonify({"error": "Quest sudah gagal (deadline terlewat)"}), 400
    if now > quest[10]:
        conn.close(); return jsonify({"error": f"Deadline {quest[10]} sudah lewat!"}), 400

    c.execute("SELECT * FROM player WHERE id=1")
    p = c.fetchone()
    level, exp, agama, it_skill, disiplin, akhlak = p[2], p[3], p[4], p[5], p[6], p[7]

    new_exp    = exp      + quest[3]
    new_agama  = agama    + quest[4]
    new_it     = it_skill + quest[5]
    new_dis    = disiplin + quest[6]
    new_akhlak = akhlak   + quest[7]

    level_ups, status_changes, old_status = [], [], get_status(level)
    while new_exp >= exp_needed(level):
        new_exp -= exp_needed(level)
        level   += 1
        level_ups.append(level)
        ns = get_status(level)
        if ns != old_status:
            status_changes.append(ns); old_status = ns

    new_status = get_status(level)
    c.execute("UPDATE player SET level=?,exp=?,agama=?,it_skill=?,disiplin=?,akhlak=?,status=? WHERE id=1",
              (level, new_exp, new_agama, new_it, new_dis, new_akhlak, new_status))
    c.execute("UPDATE quest SET completed=1 WHERE id=?", (qid,))
    conn.commit(); conn.close()

    return jsonify({
        "success": True, "level_ups": level_ups,
        "status_changes": status_changes, "new_level": level, "new_exp": new_exp
    })

@app.route("/api/violations")
def get_violations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM violation ORDER BY id DESC LIMIT 30")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id":r[0],"title":r[1],"exp_penalty":r[2],"date":r[3]} for r in rows])

@app.route("/api/violation/add", methods=["POST"])
def add_violation():
    data    = request.json
    title   = data.get("title")
    penalty = data.get("exp_penalty", 0)
    tgl     = today()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT exp FROM player WHERE id=1")
    exp     = c.fetchone()[0]
    new_exp = max(0, exp - penalty)
    c.execute("INSERT INTO violation (title,exp_penalty,violation_date) VALUES (?,?,?)", (title, penalty, tgl))
    c.execute("UPDATE player SET exp=? WHERE id=1", (new_exp,))
    conn.commit(); conn.close()
    return jsonify({"success": True, "new_exp": new_exp})

@app.route("/api/reset_quests", methods=["POST"])
def reset_quests():
    tgl = today()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM quest WHERE quest_date=?", (tgl,))
    conn.commit(); conn.close()
    seed_quests()
    return jsonify({"success": True})

if __name__ == "__main__":
    init_db()
    print("\n" + "="*45)
    print("  SANTRI QUEST - Shadow System")
    print("  Buka browser: http://localhost:5000")
    print("="*45 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)