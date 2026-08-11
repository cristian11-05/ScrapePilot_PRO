from .db import (get_site, previous_scan, add_scan, add_job, add_snapshot, 
                 add_change, add_opportunity, lowest_price_history)
from .scraper import scan_url
from .alerts import dispatch_opportunity_alert

def run_scan(site_id):
    site = get_site(site_id)
    if not site:
        raise ValueError("Sitio no encontrado")
    
    try:
        r = scan_url(site["url"], site.get("price_selector", ""), site.get("title_selector", ""), site.get("stock_selector", ""))
        prev = previous_scan(site_id)
        
        changed = int(bool(prev and prev["content_hash"] != r["content_hash"]))
        r["changed"] = changed
        r["price_changed"] = 0
        r["price_direction"] = ""
        r["notes"] = r.get("notes", "")
        
        score = 0
        reasons = []
        
        is_new_product = prev is None
        if is_new_product:
            score += 20
            reasons.append("Nuevo producto descubierto (+20)")
            
        old_price = prev.get("price_value") if prev else None
        new_price = r.get("price_value")
        
        if old_price is not None and new_price is not None:
            if new_price != old_price:
                r["price_changed"] = 1
                if new_price < old_price:
                    r["price_direction"] = "down"
                    r["notes"] += f" Precio bajó de {old_price} a {new_price}."
                    drop_pct = ((old_price - new_price) / old_price) * 100
                    if drop_pct >= 30:
                        score += 45
                        reasons.append(f"Fuerte caída de precio del {drop_pct:.1f}% (+45)")
                    elif drop_pct >= 15:
                        score += 35
                        reasons.append(f"Caída de precio del {drop_pct:.1f}% (+35)")
                    elif drop_pct >= 5:
                        score += 20
                        reasons.append(f"Ligera caída de precio del {drop_pct:.1f}% (+20)")
                else:
                    r["price_direction"] = "up"
                    r["notes"] += f" Precio subió de {old_price} a {new_price}."
                    
        if new_price is not None:
            historical_min = lowest_price_history(site_id)
            if historical_min is not None and new_price <= historical_min and new_price < (old_price or float('inf')):
                score += 25
                reasons.append("Precio mínimo histórico alcanzado (+25)")
                
        old_stock = prev.get("stock_status") if prev else "available"
        new_stock = r.get("stock_status", "available")
        
        if old_stock != "available" and new_stock == "available":
            score += 30
            reasons.append("Volvió a estar en stock (+30)")
            
        r["opportunity_score"] = min(score, 100)
        
        sid = add_scan(site_id, r)
        
        add_snapshot(site_id, sid, r["content_hash"], r["title"], r["price_text"], r["price_value"], r["stock_status"])
        
        change_id = None
        if r["price_changed"]:
            drop_pct = ((old_price - new_price) / old_price * 100) if old_price and new_price < old_price else 0
            change_id = add_change(site_id, sid, "price_drop" if r["price_direction"]=="down" else "price_increase", 
                                   "price", old_price, new_price, drop_pct)
        elif old_stock != new_stock:
            change_id = add_change(site_id, sid, "stock_change", "stock", old_stock, new_stock, 0)
        elif is_new_product:
            change_id = add_change(site_id, sid, "new_item", "item", None, new_price, 0)
            
        if score > 0:
            if score >= 85: priority = "HIGH_PRIORITY"
            elif score >= 70: priority = "IMPORTANT"
            elif score >= 50: priority = "MODERATE"
            elif score >= 30: priority = "LOW"
            else: priority = "IRRELEVANT"
            
            reason_str = ", ".join(reasons)
            opp = {
                "score": score,
                "priority": priority,
                "reason": reason_str
            }
            add_opportunity(site_id, sid, change_id, score, priority, reason_str)
            
            if score >= site.get("alert_threshold", 50):
                try:
                    dispatch_opportunity_alert(site, r, opp, None)
                except Exception as e:
                    pass
            
        add_job(site_id, "ok", f"Scan #{sid} completado. Score: {score}")
        return r
    except Exception as e:
        add_scan(site_id, {"status": "error", "error": str(e), "opportunity_score": 0})
        add_job(site_id, "error", str(e))
        raise
