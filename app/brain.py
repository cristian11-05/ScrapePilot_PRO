import logging
import random
import time
from .discovery import discover_and_add
from .db import list_sites
from .engine import run_scan
from .pipeline import build_dataset

import os
import json

logger = logging.getLogger("scrapepilot.brain")

class NicheIdea:
    def __init__(self, query, price_cents):
        self.query = query
        self.price_cents = price_cents

def get_profitable_niche() -> NicheIdea:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents="""Eres el CEO de un Data Marketplace B2B. Tu objetivo es MAXIMIZAR GANANCIAS.
Elige un nicho de alto valor comercial en Latinoamérica. Sé específico en la industria y ciudad.
Fija un precio premium en céntimos (entre 1990 y 9990, donde 1990 = S/ 19.90).

Responde SOLO con JSON válido, sin markdown:
{"query": "Industria específica en Ciudad", "price_cents": 4990}""",
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
            data = json.loads(raw)
            return NicheIdea(query=data["query"], price_cents=int(data["price_cents"]))
        except Exception as e:
            logger.error(f"Error generando nicho con Gemini: {e}")
            
    # Fallback
    INDUSTRIAS = ["Clínicas Odontológicas", "Agencias de Marketing Digital", "Inmobiliarias", "Restaurantes de Lujo"]
    UBICACIONES = ["Lima", "Bogotá", "Santiago", "Buenos Aires", "Ciudad de México"]
    return NicheIdea(query=f"{random.choice(INDUSTRIAS)} en {random.choice(UBICACIONES)}", price_cents=4990)

def run_brain_cycle():
    """
    El ciclo vital de la IA.
    1. Piensa un nicho.
    2. Busca las URLs.
    3. Extrae la data.
    4. Limpia y Empaqueta.
    """
    niche = get_profitable_niche()
    query = niche.query
    
    logger.info("🧠 EL CEREBRO HA DESPERTADO.")
    logger.info(f"🧠 IDEA GENERADA: Voy a construir un dataset sobre '{query}'.")
    
    # 1. Descubrimiento
    logger.info("🧠 FASE 1: Descubrimiento en curso...")
    res = discover_and_add(query, max_results=50, price_cents=niche.price_cents) # 50 resultados top
    if res.get("status") != "ok" or res.get("added", 0) == 0:
        logger.warning("🧠 El cerebro no encontró datos suficientes para esta idea. Abortando ciclo.")
        return
        
    dataset_id = res["dataset_id"]
    added_sites = res["urls"]
    
    logger.info(f"🧠 FASE 1 COMPLETADA: {len(added_sites)} sitios descubiertos. Dataset ID: {dataset_id}")
    
    # 2. Extracción (Selenium)
    logger.info("🧠 FASE 2: Extracción profunda iniciada...")
    for s in added_sites:
        try:
            logger.info(f"🧠 Escaneando {s['url']}...")
            run_scan(s["id"])
            time.sleep(2) # Pausa amigable entre peticiones
        except Exception as e:
            logger.error(f"Error escaneando {s['url']}: {e}")
            
    logger.info("🧠 FASE 2 COMPLETADA.")
    
    # 3. Limpieza y Publicación (Pandas)
    logger.info("🧠 FASE 3: Empaquetando y publicando dataset...")
    try:
        build_res = build_dataset(dataset_id)
        if build_res["status"] == "ok":
            logger.info(f"🧠 FASE 3 COMPLETADA. ¡El dataset '{query}' está ahora a la venta en la tienda pública!")
        else:
            logger.warning(f"🧠 FASE 3 FALLÓ: {build_res.get('message')}")
    except Exception as e:
        logger.error(f"Error construyendo dataset: {e}")
        
    logger.info("🧠 CICLO DEL CEREBRO FINALIZADO CON ÉXITO. Volviendo a dormir.")
