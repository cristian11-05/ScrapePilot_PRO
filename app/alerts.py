import logging
import urllib.parse
import requests
from .config import (
    WHATSAPP_PHONE,
    WHATSAPP_API_KEY,
    CALLMEBOT_API_KEY,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    WEBHOOK_URL
)

logger = logging.getLogger("scrapepilot.alerts")

def format_whatsapp_number(phone_str):
    phone_clean = ''.join(filter(str.isdigit, str(phone_str or WHATSAPP_PHONE or "918762620")))
    if len(phone_clean) == 9 and phone_clean.startswith("9"):
        return f"51{phone_clean}"
    return phone_clean or "51918762620"

def send_whatsapp(message, phone=None, api_key=None):
    target_phone = format_whatsapp_number(phone)
    key = api_key or CALLMEBOT_API_KEY or WHATSAPP_API_KEY
    
    encoded_text = urllib.parse.quote(message)
    success = False
    
    # Method 1: CallMeBot WhatsApp API (Free instant WhatsApp gateway)
    if key:
        url = f"https://api.callmebot.com/whatsapp.php?phone={target_phone}&text={encoded_text}&apikey={key}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                logger.info(f"WhatsApp sent via CallMeBot to {target_phone}")
                success = True
        except Exception as e:
            logger.warning(f"CallMeBot WhatsApp error: {e}")
            
    # Method 2: Fallback to WhatsApp Direct Webhook Gateway if configured
    if not success and WEBHOOK_URL:
        try:
            r = requests.post(WEBHOOK_URL, json={
                "type": "whatsapp",
                "phone": target_phone,
                "message": message
            }, timeout=10)
            if r.status_code in (200, 201, 202):
                logger.info(f"WhatsApp notification forwarded to Webhook for {target_phone}")
                success = True
        except Exception as e:
            logger.warning(f"WhatsApp Webhook error: {e}")
            
    logger.info(f"[SIMULATED WHATSAPP DISPATCH] To: +{target_phone}\nBody:\n{message}")
    return success

def send_telegram(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.warning(f"Telegram alert error: {e}")
        return False

def send_webhook(payload):
    if not WEBHOOK_URL:
        return False
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        return r.status_code in (200, 201, 202)
    except Exception as e:
        logger.warning(f"Webhook alert error: {e}")
        return False

def dispatch_opportunity_alert(site, scan, opp, change_info=None):
    title = scan.get("title") or site.get("name") or "Sitio Monitoreado"
    score = opp.get("score") or scan.get("opportunity_score") or 0
    priority = opp.get("priority") or "OPORTUNIDAD"
    price = scan.get("price_text") or "N/A"
    direction = scan.get("price_direction") or ""
    
    emoji = "🔥" if score >= 85 else "⭐" if score >= 70 else "⚡"
    
    wa_msg = f"{emoji} *SCRAPEPILOT PRO — ALERTA*\n\n"
    wa_msg += f"📍 *Fuente:* {site.get('name')}\n"
    wa_msg += f"🏷️ *Producto:* {title}\n"
    wa_msg += f"💰 *Precio actual:* {price}\n"
    if direction:
        wa_msg += f"📈 *Tendencia:* {direction.upper()}\n"
    wa_msg += f"⭐ *Opportunity Score:* {score}/100\n"
    wa_msg += f"📝 *Detalle:* {opp.get('reason') or 'Cambio detectado'}\n\n"
    wa_msg += f"🔗 *Ver en sitio:* {site.get('url')}"
    
    phone = site.get("target_phone") or WHATSAPP_PHONE or "918762620"
    
    send_whatsapp(wa_msg, phone=phone)
    send_telegram(f"<b>{emoji} SCRAPEPILOT PRO</b>\n\n<b>Fuente:</b> {site.get('name')}\n<b>Precio:</b> {price}\n<b>Score:</b> {score}/100\n<b>Razon:</b> {opp.get('reason')}")
    send_webhook({
        "event": "opportunity_detected",
        "site": site,
        "scan": scan,
        "opportunity": opp,
        "change": change_info
    })
