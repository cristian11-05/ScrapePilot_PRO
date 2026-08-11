import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from .config import DATABASE_URL

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "scrapepilot.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Normalize CockroachDB URL for libpq
db_url = DATABASE_URL
if "cockroachlabs.cloud" in db_url and "sslmode=verify-full" in db_url:
    db_url = db_url.replace("sslmode=verify-full", "sslmode=require")

IS_POSTGRES = db_url.startswith("postgresql://") or db_url.startswith("postgres://")

def connect():
    if IS_POSTGRES:
        try:
            c = psycopg2.connect(db_url, connect_timeout=10)
            return c, True
        except Exception as e:
            print(f"Error connecting to CockroachDB ({e}), falling back to SQLite.")
            c = sqlite3.connect(DB_PATH, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            return c, False
    else:
        c = sqlite3.connect(DB_PATH, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c, False

def execute_sql(sql_pg, sql_lite, params=()):
    conn, is_pg = connect()
    try:
        sql = sql_pg if is_pg else sql_lite
        if is_pg:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                conn.commit()
                try:
                    res = cur.fetchall()
                    return [dict(r) for r in res]
                except Exception:
                    return []
        else:
            with conn:
                cur = conn.execute(sql, params)
                try:
                    res = cur.fetchall()
                    return [dict(r) for r in res]
                except Exception:
                    return []
    finally:
        conn.close()

def execute_insert(sql_pg, sql_lite, params=()):
    conn, is_pg = connect()
    try:
        if is_pg:
            with conn.cursor() as cur:
                cur.execute(sql_pg + " RETURNING id", params)
                last_id = cur.fetchone()[0]
                conn.commit()
                return last_id
        else:
            with conn:
                cur = conn.execute(sql_lite, params)
                return cur.lastrowid
    finally:
        conn.close()

def init_db():
    conn, is_pg = connect()
    try:
        if is_pg:
            with conn.cursor() as cur:
                # Migration: Add new columns if they don't exist
                for col, typ in [("company_name", "VARCHAR(255) DEFAULT ''"), ("phone", "VARCHAR(100) DEFAULT ''"), ("email", "VARCHAR(255) DEFAULT ''"), ("address", "TEXT DEFAULT ''")]:
                    try:
                        cur.execute(f"ALTER TABLE scans ADD COLUMN IF NOT EXISTS {col} {typ}")
                    except Exception:
                        pass
                conn.commit()
                cur.execute("""
                CREATE TABLE IF NOT EXISTS sites (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    price_selector VARCHAR(255) DEFAULT '',
                    title_selector VARCHAR(255) DEFAULT '',
                    stock_selector VARCHAR(255) DEFAULT '',
                    interval_minutes INT DEFAULT 60,
                    active INT DEFAULT 1,
                    target_phone VARCHAR(50) DEFAULT '918762620',
                    alert_threshold INT DEFAULT 50,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS scans (
                    id SERIAL PRIMARY KEY,
                    site_id INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
                    final_url TEXT,
                    title TEXT,
                    price_text VARCHAR(255),
                    price_value DOUBLE PRECISION,
                    stock_status VARCHAR(100) DEFAULT 'available',
                    content_hash VARCHAR(128),
                    word_count INT DEFAULT 0,
                    links_count INT DEFAULT 0,
                    opportunity_score DOUBLE PRECISION DEFAULT 0,
                    changed INT DEFAULT 0,
                    price_changed INT DEFAULT 0,
                    price_direction VARCHAR(20) DEFAULT '',
                    status VARCHAR(50) DEFAULT 'ok',
                    error TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    company_name VARCHAR(255) DEFAULT '',
                    phone VARCHAR(100) DEFAULT '',
                    email VARCHAR(255) DEFAULT '',
                    address TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id SERIAL PRIMARY KEY,
                    site_id INT NOT NULL,
                    scan_id INT NOT NULL,
                    content_hash VARCHAR(128),
                    title TEXT,
                    price_text VARCHAR(255),
                    price_value DOUBLE PRECISION,
                    stock_status VARCHAR(100),
                    raw_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS changes (
                    id SERIAL PRIMARY KEY,
                    site_id INT NOT NULL,
                    scan_id INT NOT NULL,
                    change_type VARCHAR(50) NOT NULL,
                    field_name VARCHAR(50) NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    percentage_change DOUBLE PRECISION DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id SERIAL PRIMARY KEY,
                    site_id INT NOT NULL,
                    scan_id INT NOT NULL,
                    change_id INT,
                    score DOUBLE PRECISION NOT NULL,
                    priority VARCHAR(50) NOT NULL,
                    reason TEXT,
                    status VARCHAR(50) DEFAULT 'NEW',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    site_id INT NOT NULL,
                    ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50),
                    message TEXT
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    category VARCHAR(100) DEFAULT 'general',
                    search_query TEXT DEFAULT '',
                    record_count INT DEFAULT 0,
                    price_cents INT DEFAULT 990,
                    file_path TEXT DEFAULT '',
                    status VARCHAR(50) DEFAULT 'building',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS purchases (
                    id SERIAL PRIMARY KEY,
                    dataset_id INT NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    amount_cents INT NOT NULL,
                    charge_id VARCHAR(255) DEFAULT '',
                    access_token VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                conn.commit()
        else:
            with conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    price_selector TEXT DEFAULT '',
                    title_selector TEXT DEFAULT '',
                    stock_selector TEXT DEFAULT '',
                    interval_minutes INTEGER DEFAULT 60,
                    active INTEGER DEFAULT 1,
                    target_phone TEXT DEFAULT '918762620',
                    alert_threshold INTEGER DEFAULT 50,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    final_url TEXT,
                    title TEXT,
                    price_text TEXT,
                    price_value REAL,
                    stock_status TEXT DEFAULT 'available',
                    content_hash TEXT,
                    word_count INTEGER DEFAULT 0,
                    links_count INTEGER DEFAULT 0,
                    opportunity_score REAL DEFAULT 0,
                    changed INTEGER DEFAULT 0,
                    price_changed INTEGER DEFAULT 0,
                    price_direction TEXT DEFAULT '',
                    status TEXT DEFAULT 'ok',
                    error TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    company_name TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    address TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    scan_id INTEGER NOT NULL,
                    content_hash TEXT,
                    title TEXT,
                    price_text TEXT,
                    price_value REAL,
                    stock_status TEXT,
                    raw_text TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    scan_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    percentage_change REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    scan_id INTEGER NOT NULL,
                    change_id INTEGER,
                    score REAL NOT NULL,
                    priority TEXT NOT NULL,
                    reason TEXT,
                    status TEXT DEFAULT 'NEW',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    ran_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    message TEXT
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'general',
                    search_query TEXT DEFAULT '',
                    record_count INTEGER DEFAULT 0,
                    price_cents INTEGER DEFAULT 990,
                    file_path TEXT DEFAULT '',
                    status TEXT DEFAULT 'building',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    charge_id TEXT DEFAULT '',
                    access_token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """)
    finally:
        conn.close()

def add_site(name, url, price_selector="", title_selector="", stock_selector="", interval_minutes=60, target_phone="918762620", alert_threshold=50):
    sql_pg = "INSERT INTO sites (name, url, price_selector, title_selector, stock_selector, interval_minutes, target_phone, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    sql_lite = "INSERT INTO sites (name, url, price_selector, title_selector, stock_selector, interval_minutes, target_phone, alert_threshold) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    params = (name, url, price_selector, title_selector, stock_selector, interval_minutes, target_phone, alert_threshold)
    return execute_insert(sql_pg, sql_lite, params)

def list_sites():
    return execute_sql("SELECT * FROM sites ORDER BY id DESC", "SELECT * FROM sites ORDER BY id DESC")

def get_site(site_id):
    res = execute_sql("SELECT * FROM sites WHERE id = %s", "SELECT * FROM sites WHERE id = ?", (site_id,))
    return res[0] if res else None

def update_site(site_id, **fields):
    allowed = {"name", "url", "price_selector", "title_selector", "stock_selector", "interval_minutes", "active", "target_phone", "alert_threshold"}
    fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not fields:
        return
    sets_pg = [f"{k} = %s" for k in fields.keys()]
    sets_lite = [f"{k} = ?" for k in fields.keys()]
    vals = list(fields.values()) + [site_id]
    
    sql_pg = f"UPDATE sites SET {', '.join(sets_pg)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
    sql_lite = f"UPDATE sites SET {', '.join(sets_lite)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    execute_sql(sql_pg, sql_lite, tuple(vals))

def delete_site(site_id):
    execute_sql("DELETE FROM opportunities WHERE site_id = %s", "DELETE FROM opportunities WHERE site_id = ?", (site_id,))
    execute_sql("DELETE FROM changes WHERE site_id = %s", "DELETE FROM changes WHERE site_id = ?", (site_id,))
    execute_sql("DELETE FROM snapshots WHERE site_id = %s", "DELETE FROM snapshots WHERE site_id = ?", (site_id,))
    execute_sql("DELETE FROM scans WHERE site_id = %s", "DELETE FROM scans WHERE site_id = ?", (site_id,))
    execute_sql("DELETE FROM jobs WHERE site_id = %s", "DELETE FROM jobs WHERE site_id = ?", (site_id,))
    execute_sql("DELETE FROM sites WHERE id = %s", "DELETE FROM sites WHERE id = ?", (site_id,))

def previous_scan(site_id):
    res = execute_sql("SELECT * FROM scans WHERE site_id = %s ORDER BY id DESC LIMIT 1", "SELECT * FROM scans WHERE site_id = ? ORDER BY id DESC LIMIT 1", (site_id,))
    return res[0] if res else None

def lowest_price_history(site_id):
    res = execute_sql("SELECT MIN(price_value) as min_val FROM scans WHERE site_id = %s AND price_value IS NOT NULL AND price_value > 0",
                      "SELECT MIN(price_value) as min_val FROM scans WHERE site_id = ? AND price_value IS NOT NULL AND price_value > 0", (site_id,))
    if res and res[0].get("min_val") is not None:
        return float(res[0]["min_val"])
    return None

def add_scan(site_id, r):
    sql_pg = """
        INSERT INTO scans (site_id, final_url, title, price_text, price_value, stock_status, 
                           content_hash, word_count, links_count, opportunity_score, changed, price_changed, price_direction, status, error, notes,
                           company_name, phone, email, address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    sql_lite = """
        INSERT INTO scans (site_id, final_url, title, price_text, price_value, stock_status, 
                           content_hash, word_count, links_count, opportunity_score, changed, price_changed, price_direction, status, error, notes,
                           company_name, phone, email, address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        site_id, r.get("final_url"), r.get("title"), r.get("price_text"), 
        r.get("price_value"), r.get("stock_status"), r.get("content_hash"), 
        r.get("word_count",0), r.get("links_count",0), r.get("opportunity_score",0), 
        r.get("changed",0), r.get("price_changed",0), r.get("price_direction",""),
        r.get("status","ok"), r.get("error",""), r.get("notes",""),
        r.get("company_name",""), r.get("phone",""), r.get("email",""), r.get("address","")
    )
    return execute_insert(sql_pg, sql_lite, params)

def add_snapshot(site_id, scan_id, content_hash, title, price_text, price_value, stock_status, raw_text=""):
    sql_pg = "INSERT INTO snapshots (site_id, scan_id, content_hash, title, price_text, price_value, stock_status, raw_text) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    sql_lite = "INSERT INTO snapshots (site_id, scan_id, content_hash, title, price_text, price_value, stock_status, raw_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    params = (site_id, scan_id, content_hash, title, price_text, price_value, stock_status, raw_text[:2000])
    return execute_insert(sql_pg, sql_lite, params)

def add_change(site_id, scan_id, change_type, field_name, old_value, new_value, percentage_change=0.0):
    sql_pg = "INSERT INTO changes (site_id, scan_id, change_type, field_name, old_value, new_value, percentage_change) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    sql_lite = "INSERT INTO changes (site_id, scan_id, change_type, field_name, old_value, new_value, percentage_change) VALUES (?, ?, ?, ?, ?, ?, ?)"
    params = (site_id, scan_id, change_type, field_name, str(old_value) if old_value is not None else "", str(new_value) if new_value is not None else "", float(percentage_change))
    return execute_insert(sql_pg, sql_lite, params)

def add_opportunity(site_id, scan_id, change_id, score, priority, reason, status="NEW"):
    sql_pg = "INSERT INTO opportunities (site_id, scan_id, change_id, score, priority, reason, status) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    sql_lite = "INSERT INTO opportunities (site_id, scan_id, change_id, score, priority, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
    params = (site_id, scan_id, change_id, score, priority, reason, status)
    return execute_insert(sql_pg, sql_lite, params)

def opportunities(limit=50):
    sql_pg = """
        SELECT o.id as opp_id, o.score as opportunity_score, o.priority, o.reason, o.status as opp_status, o.created_at,
               sc.price_text, sc.price_value, sc.title, sc.price_direction, sc.changed, sc.stock_status,
               s.name, s.url, s.target_phone
        FROM opportunities o
        JOIN scans sc ON sc.id = o.scan_id
        JOIN sites s ON s.id = o.site_id
        ORDER BY o.score DESC, o.id DESC LIMIT %s
    """
    sql_lite = """
        SELECT o.id as opp_id, o.score as opportunity_score, o.priority, o.reason, o.status as opp_status, o.created_at,
               sc.price_text, sc.price_value, sc.title, sc.price_direction, sc.changed, sc.stock_status,
               s.name, s.url, s.target_phone
        FROM opportunities o
        JOIN scans sc ON sc.id = o.scan_id
        JOIN sites s ON s.id = o.site_id
        ORDER BY o.score DESC, o.id DESC LIMIT ?
    """
    return execute_sql(sql_pg, sql_lite, (limit,))

def history(site_id, limit=100):
    return execute_sql("SELECT * FROM scans WHERE site_id = %s ORDER BY id DESC LIMIT %s",
                       "SELECT * FROM scans WHERE site_id = ? ORDER BY id DESC LIMIT ?", (site_id, limit))

def list_changes(site_id=None, limit=50):
    if site_id:
        return execute_sql("SELECT c.*, s.name FROM changes c JOIN sites s ON s.id = c.site_id WHERE c.site_id = %s ORDER BY c.id DESC LIMIT %s",
                           "SELECT c.*, s.name FROM changes c JOIN sites s ON s.id = c.site_id WHERE c.site_id = ? ORDER BY c.id DESC LIMIT ?", (site_id, limit))
    return execute_sql("SELECT c.*, s.name FROM changes c JOIN sites s ON s.id = c.site_id ORDER BY c.id DESC LIMIT %s",
                       "SELECT c.*, s.name FROM changes c JOIN sites s ON s.id = c.site_id ORDER BY c.id DESC LIMIT ?", (limit,))

def stats():
    conn, is_pg = connect()
    try:
        def fetch_val(q):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute(q)
                    row = cur.fetchone()
                    return row[0] if row else 0
            else:
                with conn:
                    row = conn.execute(q).fetchone()
                    return row[0] if row else 0

        s_count = fetch_val("SELECT COUNT(*) FROM sites")
        s_active = fetch_val("SELECT COUNT(*) FROM sites WHERE active=1")
        sc_count = fetch_val("SELECT COUNT(*) FROM scans")
        ch_count = fetch_val("SELECT COUNT(*) FROM changes")
        op_high = fetch_val("SELECT COUNT(*) FROM opportunities WHERE score >= 70")
        err_count = fetch_val("SELECT COUNT(*) FROM scans WHERE status != 'ok'")
        avg_score = fetch_val("SELECT COALESCE(AVG(opportunity_score), 0) FROM scans WHERE status='ok'")
        
        return {
            "sites": s_count,
            "active": s_active,
            "scans": sc_count,
            "changes": ch_count,
            "high_opportunities": op_high,
            "errors": err_count,
            "average_score": round(float(avg_score or 0), 1),
            "is_postgres": is_pg
        }
    finally:
        conn.close()

def add_job(site_id, status, message):
    sql_pg = "INSERT INTO jobs (site_id, status, message) VALUES (%s, %s, %s)"
    sql_lite = "INSERT INTO jobs (site_id, status, message) VALUES (?, ?, ?)"
    return execute_insert(sql_pg, sql_lite, (site_id, status, message))

def jobs(limit=50):
    sql_pg = "SELECT j.*, s.name FROM jobs j JOIN sites s ON s.id = j.site_id ORDER BY j.id DESC LIMIT %s"
    sql_lite = "SELECT j.*, s.name FROM jobs j JOIN sites s ON s.id = j.site_id ORDER BY j.id DESC LIMIT ?"
    return execute_sql(sql_pg, sql_lite, (limit,))

# --- Dataset CRUD ---
def add_dataset(title, description, category, search_query, price_cents=990):
    sql_pg = "INSERT INTO datasets (title, description, category, search_query, price_cents) VALUES (%s, %s, %s, %s, %s)"
    sql_lite = "INSERT INTO datasets (title, description, category, search_query, price_cents) VALUES (?, ?, ?, ?, ?)"
    return execute_insert(sql_pg, sql_lite, (title, description, category, search_query, price_cents))

def update_dataset(ds_id, **fields):
    allowed = {"title", "description", "category", "record_count", "price_cents", "file_path", "status"}
    fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not fields:
        return
    sets_pg = [f"{k} = %s" for k in fields.keys()]
    sets_lite = [f"{k} = ?" for k in fields.keys()]
    vals = list(fields.values()) + [ds_id]
    sql_pg = f"UPDATE datasets SET {', '.join(sets_pg)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
    sql_lite = f"UPDATE datasets SET {', '.join(sets_lite)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    execute_sql(sql_pg, sql_lite, tuple(vals))

def list_datasets():
    return execute_sql("SELECT * FROM datasets ORDER BY id DESC", "SELECT * FROM datasets ORDER BY id DESC")

def get_dataset(ds_id):
    res = execute_sql("SELECT * FROM datasets WHERE id = %s", "SELECT * FROM datasets WHERE id = ?", (ds_id,))
    return res[0] if res else None

def add_purchase(dataset_id, email, amount_cents, charge_id, access_token, expires_at):
    sql_pg = "INSERT INTO purchases (dataset_id, email, amount_cents, charge_id, access_token, expires_at) VALUES (%s, %s, %s, %s, %s, %s)"
    sql_lite = "INSERT INTO purchases (dataset_id, email, amount_cents, charge_id, access_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)"
    return execute_insert(sql_pg, sql_lite, (dataset_id, email, amount_cents, charge_id, access_token, expires_at))

def get_purchase_by_token(token):
    res = execute_sql("SELECT * FROM purchases WHERE access_token = %s", "SELECT * FROM purchases WHERE access_token = ?", (token,))
    return res[0] if res else None

def list_purchases(limit=100):
    return execute_sql("SELECT p.*, d.title as dataset_title FROM purchases p JOIN datasets d ON d.id = p.dataset_id ORDER BY p.id DESC LIMIT %s",
                       "SELECT p.*, d.title as dataset_title FROM purchases p JOIN datasets d ON d.id = p.dataset_id ORDER BY p.id DESC LIMIT ?", (limit,))
