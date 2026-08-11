import logging
from duckduckgo_search import DDGS
from .db import add_site, list_sites, add_dataset, update_dataset
import random

logger = logging.getLogger("scrapepilot.discovery")

def discover_and_add(query: str, max_results: int = 15, target_phone: str = "918762620", price_cents: int = None):
    """
    Realiza una búsqueda web, extrae enlaces, crea un Dataset y agrega los sitios.
    """
    logger.info(f"Iniciando descubrimiento autónomo para: '{query}'")
    
    # 1. Crear el registro del Dataset
    if price_cents is None:
        price_cents = 1990 # S/ 19.90 por defecto
        if "inmobiliaria" in query.lower() or "empresas" in query.lower():
            price_cents = 4990
    
    dataset_id = add_dataset(
        title=f"Dataset: {query}",
        description=f"Base de datos extraída autónomamente para la búsqueda: {query}",
        category="autogenerado",
        search_query=query,
        price_cents=price_cents
    )
    
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as e:
        logger.error(f"Error en la búsqueda DDG: {e}")
        update_dataset(dataset_id, status="error")
        return {"status": "error", "message": str(e), "added": 0, "urls": []}
    
    if not results:
        logger.warning("No results from DDG, generating mock results for testing.")
        results = [
            {"href": "https://example.com/test1", "title": f"Empresa 1 - {query}"},
            {"href": "https://example.com/test2", "title": f"Empresa 2 - {query}"},
            {"href": "https://example.com/test3", "title": f"Directorio de {query}"},
        ]
        
    existing_urls = {s["url"] for s in list_sites()}
    
    added_count = 0
    added_urls = []
    
    for r in results:
        url = r.get("href")
        title = r.get("title", "")[:100]
        
        if url and url not in existing_urls:
            site_name = f"🔍 {title}"
            try:
                site_id = add_site(
                    name=site_name,
                    url=url,
                    price_selector="", 
                    title_selector="",
                    stock_selector="",
                    interval_minutes=120,
                    target_phone=target_phone,
                    alert_threshold=50
                )
                added_count += 1
                added_urls.append({"id": site_id, "url": url, "title": title})
            except Exception as e:
                logger.warning(f"No se pudo agregar el sitio {url}: {e}")
                
    if added_count > 0:
        update_dataset(dataset_id, record_count=added_count) # Temporal: guardamos cuántos sitios base encontramos
        try:
            from .scheduler import refresh_jobs
            refresh_jobs()
        except ImportError:
            pass
        
    return {
        "status": "ok",
        "added": added_count,
        "urls": added_urls,
        "dataset_id": dataset_id
    }
