from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse, PlainTextResponse
from pydantic import BaseModel, HttpUrl, Field
import csv, io, hashlib, time, os, requests as http_requests
from datetime import datetime
from .db import init_db, add_site, list_sites, get_site, update_site, delete_site, history, stats, jobs
from .db import list_datasets, get_dataset, update_dataset, add_purchase, get_purchase_by_token, list_purchases
from .engine import run_scan
from .scheduler import start as start_scheduler, refresh_jobs
from .discovery import discover_and_add
from .pipeline import build_dataset
from .brain import run_brain_cycle
from .config import CULQI_PUBLIC_KEY, CULQI_SECRET_KEY

app = FastAPI(title="DataMarket Autonomous", version="1.1.0")

class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    price_selector: str = ""
    title_selector: str = ""
    stock_selector: str = ""
    interval_minutes: int = Field(default=60, ge=5, le=10080)
    target_phone: str = "918762620"
    alert_threshold: int = 50

class DiscoverIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)

class CulqiChargeIn(BaseModel):
    token: str
    email: str
    dataset_id: int

@app.on_event("startup")
def startup():
    init_db()
    start_scheduler()

# =============================================
# PUBLIC STOREFRONT
# =============================================
@app.get("/", response_class=HTMLResponse)
def public_storefront():
    return STOREFRONT

# =============================================
# ADMIN DASHBOARD
# =============================================
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard():
    return DASHBOARD

# =============================================
# API ENDPOINTS
# =============================================
@app.get("/api/datasets")
def api_get_datasets():
    return list_datasets()

@app.get("/api/datasets/public")
def api_get_datasets_public():
    """Returns only ready datasets without exposing exact file paths"""
    ds = list_datasets()
    return [{
        "id": d["id"],
        "title": d["title"],
        "description": d["description"],
        "record_count": d["record_count"],
        "price_cents": d["price_cents"],
        "created_at": d["created_at"]
    } for d in ds if d["status"] == "ready"]

@app.post("/api/discover")
def api_discover(d: DiscoverIn):
    try:
        res = discover_and_add(d.query)
        if res["status"] == "error":
            raise HTTPException(500, res["message"])
        return res
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/datasets/{ds_id}/build")
def api_build_dataset(ds_id: int):
    try:
        return build_dataset(ds_id)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/brain/wake")
def api_wake_brain():
    import threading
    t = threading.Thread(target=run_brain_cycle)
    t.start()
    return {"ok": True, "message": "🧠 El Cerebro se ha despertado y está operando en segundo plano."}

# =============================================
# SEO: Individual Dataset Pages (Google los indexa)
# =============================================
@app.get("/d/{ds_id}", response_class=HTMLResponse)
def seo_dataset_page(ds_id: int):
    ds = get_dataset(ds_id)
    if not ds or ds["status"] != "ready":
        raise HTTPException(404, "Dataset no encontrado")
    title = ds["title"]
    desc = ds["description"]
    price = f"S/ {ds['price_cents']/100:.2f}"
    records = ds["record_count"]
    # Get a free preview (first 3 rows from CSV)
    preview_html = ""
    if ds.get("file_path") and os.path.exists(ds["file_path"]):
        try:
            import pandas as pd
            df = pd.read_csv(ds["file_path"], nrows=3)
            # Censor emails and phones
            for col in df.columns:
                if "email" in col.lower():
                    df[col] = df[col].apply(lambda x: str(x)[:3] + "***@***.com" if pd.notna(x) and x else "")
                if "phone" in col.lower() or "tel" in col.lower():
                    df[col] = df[col].apply(lambda x: str(x)[:3] + "*****" if pd.notna(x) and x else "")
            preview_html = df.to_html(index=False, classes="preview-table", border=0)
        except Exception:
            pass
    return f'''<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - {records} registros | DataMarket</title>
<meta name="description" content="{desc}. {records} registros limpios y verificados. Descarga inmediata por {price}.">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}. {records} registros por {price}.">
<meta property="og:type" content="product">
<link rel="canonical" href="/d/{ds_id}">
<style>
:root{{--bg:#0f172a;--panel:rgba(30,41,59,0.7);--border:rgba(51,65,85,0.5);--text:#f8fafc;--brand:#3b82f6;--accent:#10b981}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}
.container{{max-width:900px;margin:auto;padding:40px 20px}}
h1{{font-size:36px;margin-bottom:16px}}
.badge{{display:inline-block;padding:6px 14px;border-radius:20px;font-size:14px;font-weight:700;background:rgba(16,185,129,0.15);color:#6ee7b7;margin-bottom:20px}}
.info{{display:flex;gap:30px;margin:24px 0;flex-wrap:wrap}}
.info div{{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:20px;flex:1;min-width:150px;text-align:center}}
.info div span{{display:block;font-size:28px;font-weight:800;color:var(--accent)}}
.info div small{{color:#94a3b8}}
.buy-btn{{display:block;width:100%;padding:18px;border:0;border-radius:12px;background:linear-gradient(135deg,var(--brand),#8b5cf6);color:#fff;font-size:20px;font-weight:800;cursor:pointer;margin:24px 0;text-align:center;text-decoration:none}}
.buy-btn:hover{{filter:brightness(1.1)}}
.preview-table{{width:100%;border-collapse:collapse;margin:16px 0}}
.preview-table th{{background:#1e293b;padding:10px;text-align:left;font-size:13px;color:#94a3b8}}
.preview-table td{{padding:10px;border-bottom:1px solid var(--border);font-size:13px}}
.blur-note{{text-align:center;padding:16px;color:#94a3b8;font-style:italic;background:rgba(59,130,246,0.05);border-radius:8px;margin-top:8px}}
</style></head><body>
<div class="container">
<a href="/" style="color:var(--brand);text-decoration:none;font-size:14px">&larr; Ver todos los datasets</a>
<h1 style="margin-top:16px">{title}</h1>
<span class="badge">✅ {records} registros verificados</span>
<p style="color:#cbd5e1;font-size:16px;line-height:1.6;margin-bottom:20px">{desc}</p>
<div class="info">
<div><span>{records}</span><small>Registros</small></div>
<div><span>{price}</span><small>Precio</small></div>
<div><span>CSV</span><small>Formato</small></div>
</div>
<h3 style="margin:24px 0 8px">🔍 Vista Previa (datos censurados)</h3>
{preview_html if preview_html else "<p style='color:#94a3b8'>Vista previa no disponible</p>"}
<p class="blur-note">🔒 Los datos completos (emails, teléfonos, direcciones) se desbloquean al comprar</p>
<a href="/" class="buy-btn">💳 Comprar por {price} — Descarga Inmediata</a>
</div></body></html>'''

@app.get("/sitemap.xml", response_class=PlainTextResponse)
def sitemap():
    ds = list_datasets()
    urls = ['<url><loc>https://datamarket.app/</loc><priority>1.0</priority></url>']
    for d in ds:
        if d["status"] == "ready":
            urls.append(f'<url><loc>https://datamarket.app/d/{d["id"]}</loc><priority>0.8</priority></url>')
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>'''
    return PlainTextResponse(content=xml, media_type="application/xml")

# =============================================
# PAYMENT & DOWNLOAD
# =============================================
@app.post("/api/pay")
def api_pay(d: CulqiChargeIn):
    ds = get_dataset(d.dataset_id)
    if not ds or ds["status"] != "ready":
        raise HTTPException(404, "Dataset no disponible")

    amount = ds["price_cents"]
    desc = ds["title"]

    try:
        # Petición a Culqi
        r = http_requests.post("https://api.culqi.com/v2/charges", json={
            "amount": amount,
            "currency_code": "PEN",
            "email": d.email,
            "source_id": d.token,
            "description": desc,
            "capture": True
        }, headers={
            "Authorization": f"Bearer {CULQI_SECRET_KEY}",
            "Content-Type": "application/json"
        }, timeout=15)

        data = r.json()

        if r.status_code in (200, 201) and data.get("id"):
            access_token = hashlib.sha256(f"{d.email}{time.time()}".encode()).hexdigest()[:32]
            expires = datetime.fromtimestamp(time.time() + 86400 * 7) # 7 days access
            
            add_purchase(d.dataset_id, d.email, amount, data["id"], access_token, expires.isoformat())

            return {
                "ok": True,
                "access_token": access_token,
                "message": f"¡Pago exitoso! Acceso garantizado por 7 días."
            }
        else:
            return {"ok": False, "message": data.get("merchant_message") or data.get("user_message") or "Pago rechazado"}
    except Exception as e:
        raise HTTPException(500, f"Error procesando pago: {str(e)}")

@app.get("/api/download/{token}")
def api_download(token: str):
    p = get_purchase_by_token(token)
    if not p:
        raise HTTPException(403, "Token inválido o expirado.")
        
    ds = get_dataset(p["dataset_id"])
    if not ds or not ds["file_path"] or not os.path.exists(ds["file_path"]):
        raise HTTPException(404, "El archivo ya no está disponible.")
        
    return FileResponse(ds["file_path"], media_type="text/csv", filename=f"dataset_{ds['id']}.csv")

@app.post("/api/scan-all")
def api_scan_all():
    out = []
    for s in list_sites():
        if s["active"]:
            try:
                out.append({"id": s["id"], "status": "ok", "result": run_scan(s["id"])})
            except Exception as e:
                out.append({"id": s["id"], "status": "error", "error": str(e)})
    return out

# =============================================
# STOREFRONT — Pública
# =============================================
STOREFRONT = r'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DataMarket — Bases de Datos Premium</title>
<style>
:root{--bg:#0f172a;--panel:rgba(30,41,59,0.7);--border:rgba(51,65,85,0.5);--text:#f8fafc;--brand:#3b82f6;--brand-glow:rgba(59,130,246,0.3);--accent:#10b981}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
header{padding:30px;text-align:center;background:linear-gradient(180deg, rgba(15,23,42,1) 0%, rgba(15,23,42,0) 100%)}
h1{font-size:48px;font-weight:900;margin-bottom:10px;background:linear-gradient(90deg, #fff, var(--brand));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
p.sub{color:#94a3b8;font-size:18px;max-width:600px;margin:auto}
main{max-width:1100px;margin:auto;padding:40px 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:24px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:24px;transition:transform 0.2s}
.card:hover{transform:translateY(-4px);border-color:var(--brand)}
.card h3{font-size:20px;color:#fff;margin-bottom:8px}
.card p{color:#cbd5e1;font-size:14px;margin-bottom:16px;line-height:1.5}
.meta{display:flex;justify-content:space-between;align-items:center;padding-top:16px;border-top:1px solid var(--border)}
.records{font-size:13px;color:#94a3b8;font-weight:600}
.price{font-size:24px;font-weight:800;color:var(--accent)}
.buy-btn{width:100%;margin-top:16px;padding:14px;border:0;border-radius:8px;background:var(--brand);color:#fff;font-weight:700;font-size:16px;cursor:pointer}
.buy-btn:hover{filter:brightness(1.1)}
/* MODAL */
.modal-bg{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:100;justify-content:center;align-items:center}
.modal-bg.show{display:flex}
.modal{background:#1e293b;border:1px solid var(--border);border-radius:16px;padding:32px;max-width:400px;width:90%;text-align:center}
.modal input{width:100%;padding:12px;margin-bottom:12px;border-radius:8px;border:1px solid var(--border);background:#0f172a;color:#fff}
.download-box{display:none;margin-top:20px;padding:20px;background:rgba(16,185,129,0.1);border:1px solid var(--accent);border-radius:12px}
.download-box a{display:inline-block;padding:12px 24px;background:var(--accent);color:#000;text-decoration:none;font-weight:700;border-radius:8px;margin-top:10px}
</style>
</head><body>
<header>
  <h1>DataMarket</h1>
  <p class="sub">Bases de datos extraídas y limpiadas listas para usar.</p>
</header>
<main>
  <div class="grid" id="dsGrid"></div>
</main>

<div class="modal-bg" id="payModal">
  <div class="modal">
    <h3 id="mTitle" style="color:#fff;margin-bottom:8px"></h3>
    <p id="mPrice" style="color:var(--accent);font-size:24px;font-weight:800;margin-bottom:20px"></p>
    <div id="payForm">
        <input type="email" id="payEmail" placeholder="Ingresa tu correo" required>
        <button class="buy-btn" onclick="processPayment()">💳 Pagar (Yape / Tarjeta)</button>
        <div id="payStatus" style="margin-top:10px;color:#94a3b8;font-size:14px"></div>
    </div>
    <div class="download-box" id="dlBox">
        <h4 style="color:var(--accent);margin-bottom:10px">✅ ¡Pago Exitoso!</h4>
        <p style="font-size:13px;color:#cbd5e1">Tu dataset está listo.</p>
        <a id="dlLink" href="#">📥 Descargar CSV</a>
    </div>
    <button style="background:none;border:0;color:#94a3b8;margin-top:20px;cursor:pointer" onclick="closeModal()">Cerrar</button>
  </div>
</div>

<script src="https://checkout.culqi.com/js/v4"></script>
<script>
let activeDsId = null;
let activePrice = null;
const CULQI_PK = ''' + f'"{CULQI_PUBLIC_KEY}"' + r''';

if(window.Culqi) {
  Culqi.publicKey = CULQI_PK;
  Culqi.settings({ title: 'DataMarket', currency: 'PEN', style: { logo: '', bannerColor: '#3b82f6', buttonBackground: '#3b82f6', buttonText: '#fff' } });
}

async function load() {
    let r = await fetch("/api/datasets/public");
    let data = await r.json();
    let grid = document.getElementById("dsGrid");
    
    if(!data.length) {
        grid.innerHTML = '<p style="color:#94a3b8">No hay datasets disponibles en este momento.</p>';
        return;
    }
    
    grid.innerHTML = data.map(d => `
        <div class="card">
            <h3>${d.title}</h3>
            <p>${d.description}</p>
            <div class="meta">
                <div class="records">📊 ${d.record_count} registros</div>
                <div class="price">S/ ${(d.price_cents/100).toFixed(2)}</div>
            </div>
            <button class="buy-btn" onclick="buy(${d.id}, '${d.title}', ${d.price_cents})">Comprar Dataset</button>
        </div>
    `).join('');
}

function buy(id, title, priceCents) {
    activeDsId = id;
    activePrice = priceCents;
    document.getElementById('mTitle').textContent = title;
    document.getElementById('mPrice').textContent = `S/ ${(priceCents/100).toFixed(2)}`;
    document.getElementById('payForm').style.display = 'block';
    document.getElementById('dlBox').style.display = 'none';
    document.getElementById('payStatus').textContent = '';
    document.getElementById('payModal').classList.add('show');
    
    if(window.Culqi) Culqi.settings({ title: 'DataMarket', currency: 'PEN', amount: priceCents });
}
function closeModal() { document.getElementById('payModal').classList.remove('show'); }

function processPayment() {
    let email = document.getElementById('payEmail').value;
    if(!email) return alert("Correo requerido");
    
    if(window.Culqi && !Culqi.publicKey.includes('xxxx')) {
        Culqi.options({ style: { logo: '' } });
        Culqi.open();
    } else {
        // DEMO MODE
        document.getElementById('payStatus').textContent = 'Procesando...';
        setTimeout(()=>confirmPayment("demo_token", email), 1000);
    }
}

async function confirmPayment(token, email) {
    try {
        let r = await fetch("/api/pay", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({token: token, email: email, dataset_id: activeDsId})
        });
        let res = await r.json();
        if(res.ok) {
            document.getElementById('payForm').style.display = 'none';
            document.getElementById('dlBox').style.display = 'block';
            document.getElementById('dlLink').href = `/api/download/${res.access_token}`;
        } else {
            document.getElementById('payStatus').textContent = 'Error: ' + res.message;
        }
    } catch(e) {
        document.getElementById('payStatus').textContent = 'Error de red';
    }
}

window.culqi = function() {
    if (Culqi.token) confirmPayment(Culqi.token.id, document.getElementById('payEmail').value);
    else if (Culqi.order) document.getElementById('payStatus').textContent = 'Procesando Yape...';
};

load();
</script></body></html>'''

# =============================================
# ADMIN DASHBOARD
# =============================================
DASHBOARD = r'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin — DataMarket</title>
<style>
:root{--bg:#0f172a;--panel:rgba(30,41,59,0.7);--border:rgba(51,65,85,0.5);--text:#f8fafc;--brand:#3b82f6;--brand-glow:rgba(59,130,246,0.3);--accent:#10b981;--danger:#ef4444}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{padding:20px 30px;background:#1e293b;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
main{max-width:1200px;margin:auto;padding:30px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:24px}
input{width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:#0f172a;color:#fff;margin-bottom:10px}
button{padding:12px 20px;border-radius:8px;border:0;background:var(--brand);color:#fff;font-weight:600;cursor:pointer}
button:hover{filter:brightness(1.1)}
table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}
.badge{padding:4px 8px;border-radius:12px;font-size:12px;font-weight:600}
.b-ready{background:rgba(16,185,129,0.2);color:#6ee7b7}
.b-build{background:rgba(245,158,11,0.2);color:#fcd34d}
</style>
</head><body>
<header>
  <h2 style="margin:0">🛠️ DataMarket Admin</h2>
  <div style="display:flex;gap:10px">
      <a href="/" style="color:var(--brand);text-decoration:none">Ver Tienda</a>
      <button onclick="scanAll()">▶️ Iniciar Extracción Global</button>
  </div>
</header>
<main>
  <div class="card" style="margin-bottom:24px;background:var(--brand-glow);border-color:var(--brand);text-align:center">
    <h2 style="font-size:24px;margin-bottom:8px">🧠 Cerebro Autónomo Zero-Touch</h2>
    <p style="font-size:15px;color:#cbd5e1;margin-bottom:20px;max-width:700px;margin-left:auto;margin-right:auto">El sistema genera sus propias ideas, extrae la data, la limpia y la publica en la tienda de forma 100% automática cada 8 horas.</p>
    <button onclick="wakeBrain()" style="font-size:18px;padding:16px 32px;border-radius:12px;background:linear-gradient(135deg,var(--brand),#8b5cf6)">⚡ Despertar Cerebro Ahora</button>
    <div id="bRes" style="margin-top:16px;color:var(--accent);font-size:15px;font-weight:600"></div>
  </div>

  <div class="card">
    <h3>Inventario de Datasets (Tu Tienda)</h3>
    <table id="dsTable"></table>
  </div>
</main>
<script>
async function load() {
    let r = await fetch("/api/datasets");
    let data = await r.json();
    let html = "<tr><th>ID</th><th>Título / Idea de la IA</th><th>Precio</th><th>Registros</th><th>Estado</th><th>Acción</th></tr>";
    
    html += data.map(d => {
        let badge = d.status === 'ready' ? '<span class="badge b-ready">Listo</span>' : '<span class="badge b-build">Construyendo</span>';
        return `<tr>
            <td>${d.id}</td>
            <td><b>${d.title}</b><br><span style="font-size:12px;color:#94a3b8">${d.search_query}</span></td>
            <td>S/ ${(d.price_cents/100).toFixed(2)}</td>
            <td>${d.record_count}</td>
            <td>${badge}</td>
            <td>
                ${d.status !== 'ready' ? `<button onclick="build(${d.id})" style="padding:6px 12px;font-size:12px;background:var(--accent)">Consolidar con Pandas</button>` : `<a href="/api/datasets/public" target="_blank" style="color:var(--brand);font-size:13px">Ver en tienda</a>`}
            </td>
        </tr>`;
    }).join('');
    
    document.getElementById('dsTable').innerHTML = html;
}

async function wakeBrain() {
    try {
        let r = await fetch("/api/brain/wake", {method: "POST"});
        let res = await r.json();
        document.getElementById('bRes').textContent = res.message;
        setTimeout(load, 5000);
    } catch(e) {
        document.getElementById('bRes').textContent = "Error despertando cerebro.";
    }
}

async function build(id) {
    try {
        let r = await fetch(`/api/datasets/${id}/build`, {method:"POST"});
        let res = await r.json();
        if(res.status === 'ok') alert(`✅ Dataset consolidado y listo para venta. ${res.records} registros válidos limpios.`);
        else alert('Error: ' + res.message);
        load();
    } catch(e) { alert(e.message); }
}

load();
</script></body></html>'''
