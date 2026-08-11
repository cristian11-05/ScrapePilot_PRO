import pandas as pd
import os
from datetime import datetime
from .db import list_sites, history, get_dataset, update_dataset

def build_dataset(dataset_id: int, export_dir="data/exports"):
    """
    Usa Pandas para estructurar y exportar el Dataset.
    En la vida real, se filtrarían los escaneos asociados a la búsqueda del dataset.
    Aquí, por simplicidad para la demo, tomamos los datos de los sitios descubiertos
    que coinciden (o simplemente todos los recientes si es pequeño).
    """
    ds = get_dataset(dataset_id)
    if not ds: return {"status": "error", "message": "Dataset no encontrado"}
    
    os.makedirs(export_dir, exist_ok=True)
    sites = list_sites()
    all_scans = []
    
    # Filtramos sitios que contengan términos de la búsqueda (simplificado)
    query_terms = ds["search_query"].lower().split()
    target_sites = [s for s in sites if any(term in s["name"].lower() or term in s["url"].lower() for term in query_terms)]
    if not target_sites:
        target_sites = sites # Fallback si no hay coincidencias exactas
        
    for s in target_sites:
        site_scans = history(s["id"], limit=50)
        for sc in site_scans:
            sc["source_name"] = s["name"]
            sc["source_url"] = s["url"]
            all_scans.append(sc)
            
    if not all_scans:
        update_dataset(dataset_id, status="empty", record_count=0)
        return {"status": "error", "message": "No hay datos para construir el dataset."}
        
    df = pd.DataFrame(all_scans)
    df = df.drop_duplicates(subset=["site_id", "content_hash"], keep="last")
    
    # Normalización con Pandas
    df["title"] = df["title"].str.strip().str.title()
    df["price_value"] = pd.to_numeric(df["price_value"], errors="coerce").fillna(0.0)
    
    # Columnas base siempre presentes
    base_cols = ["source_name", "source_url", "title", "price_value", "price_text", 
                 "word_count", "links_count", "created_at"]
    # Columnas LLM opcionales
    llm_cols = ["company_name", "phone", "email", "address"]
    
    available_cols = [c for c in base_cols + llm_cols if c in df.columns]
    clean_df = df[available_cols]
    
    csv_string = clean_df.to_csv(index=False, encoding="utf-8-sig")
    
    records = len(clean_df)
    update_dataset(dataset_id, status="ready", record_count=records, file_path="db_virtual", csv_data=csv_string)
    
    return {
        "status": "ok", 
        "csv": "db_virtual", 
        "records": records
    }

