import hashlib, re, time
from urllib.parse import urljoin, urlparse
from urllib import robotparser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from .config import USER_AGENT
import json
import os

# Initialize Gemini
gemini_client = None
try:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        from google import genai
        gemini_client = genai.Client(api_key=gemini_key)
except Exception:
    pass

def extract_data_with_llm(text: str) -> dict:
    empty = {"company_name": "", "phone": "", "email": "", "address": ""}
    if not gemini_client:
        return empty
        
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=f"""Eres un asistente experto en extracción de datos estructurados para inteligencia comercial.
Del siguiente texto web, extrae SOLO los datos reales que encuentres. Si no encuentras alguno, deja el campo vacío.
NO INVENTES datos. Responde SOLO con JSON válido, sin markdown.

Formato de respuesta:
{{"company_name": "...", "phone": "...", "email": "...", "address": "..."}}

Texto:
{text[:8000]}""",
        )
        raw = response.text.strip()
        # Clean markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        data = json.loads(raw)
        return {
            "company_name": str(data.get("company_name", ""))[:255],
            "phone": str(data.get("phone", ""))[:100],
            "email": str(data.get("email", ""))[:255],
            "address": str(data.get("address", ""))
        }
    except Exception as e:
        print(f"Error LLM Gemini: {e}")
        return empty

def get_webdriver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    # Docker specific options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def robots_allowed(url):
    p=urlparse(url); robots=f"{p.scheme}://{p.netloc}/robots.txt"
    rp=robotparser.RobotFileParser(); rp.set_url(robots)
    try: rp.read(); return rp.can_fetch(USER_AGENT,url),robots
    except Exception: return False,robots

def parse_price(v):
    if v is None:return None
    m=re.search(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?)",str(v))
    if not m:return None
    n=m.group(1).replace(" ","")
    if "," in n and "." in n:n=n.replace(".","").replace(",",".")
    elif "," in n:n=n.replace(",",".")
    try:return float(n)
    except:return None

def first_price(text):
    for p in [r"(?:S\/|S/|PEN|USD|\$)\s?\d+(?:[.,]\d{1,2})?",r"\d+(?:[.,]\d{1,2})?\s?(?:PEN|USD)"]:
        m=re.search(p,text,re.I)
        if m:return m.group(0),parse_price(m.group(0))
    return None,None

def scan_url(url, price_selector="", title_selector="", stock_selector=""):
    driver = None
    try:
        driver = get_webdriver()
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(3) # Give SPA some time to render
        html = driver.page_source
        final_url = driver.current_url
    finally:
        if driver:
            try: driver.quit()
            except: pass

    soup = BeautifulSoup(html, "html.parser")
    
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    if title_selector:
        try:
            el = soup.select_one(title_selector)
            if el: title = el.get_text(" ", strip=True)
        except: pass

    selected_price = None
    if price_selector:
        try:
            el = soup.select_one(price_selector)
            if el: selected_price = el.get_text(" ", strip=True)
        except: pass

    stock_status = "available"
    if stock_selector:
        try:
            el = soup.select_one(stock_selector)
            if el: 
                t = el.get_text(" ", strip=True).lower()
                if any(w in t for w in ["agotado", "out of stock", "no disponible"]):
                    stock_status = "out_of_stock"
        except: pass
    else:
        text_lower = soup.get_text(" ", strip=True).lower()
        if "agotado" in text_lower or "out of stock" in text_lower or "sin stock" in text_lower:
            stock_status = "out_of_stock"

    for tag in soup(["script", "style", "noscript"]): tag.decompose()
    text = soup.get_text(" ", strip=True)
    words = re.findall(r"\b[\wÀ-ÿ'-]+\b", text)
    links = {urljoin(final_url, a["href"]) for a in soup.find_all("a", href=True)
             if urlparse(urljoin(final_url, a["href"])).scheme in ("http", "https")}
           
    pt = selected_price
    pv = parse_price(pt) if pt else None
    if pt is None:
        pt, pv = first_price(text)
    
    h = hashlib.sha256(re.sub(r"\s+", " ", text).encode("utf-8", "ignore")).hexdigest()
    low = text.lower()
    score = 0
    if pv is not None: score += 30
    if len(words) >= 300: score += 15
    if len(links) >= 10: score += 10
    if any(k in low for k in ("precio", "oferta", "stock", "disponible", "producto")): score += 20
    if any(k in low for k in ("contacto", "comprar", "carrito", "whatsapp")): score += 15
    if len(text) > 5000: score += 10
    
    # 4. Extracción Semántica (LLM)
    llm_data = extract_data_with_llm(text)
    
    return {
        "final_url": final_url,
        "title": title[:300],
        "price_text": pt,
        "price_value": pv,
        "stock_status": stock_status,
        "content_hash": h,
        "word_count": len(words),
        "links_count": len(links),
        "opportunity_score": min(score, 100),
        "status": "ok",
        "notes": "Selenium + OpenAI Data Extracted.",
        "company_name": llm_data["company_name"],
        "phone": llm_data["phone"],
        "email": llm_data["email"],
        "address": llm_data["address"]
    }
