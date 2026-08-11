import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "ScrapePilot PRO")
DEFAULT_DB_URL = "postgresql://franco_huaman_tecsup:iO2El4JvzFmf5KFnBljzvQ@sonic-wilddog-29676.j77.aws-us-east-1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ScrapePilotBot/1.0")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "secreto123")

WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "918762620")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

SAAS_PLAN = os.getenv("SAAS_PLAN", "PRO")

# --- Culqi Payment Integration ---
# Usa tus llaves de Culqi (https://culqi.com) - modo TEST para desarrollo
CULQI_PUBLIC_KEY = os.getenv("CULQI_PUBLIC_KEY", "pk_test_xxxxxxxxxxxxxxxx")
CULQI_SECRET_KEY = os.getenv("CULQI_SECRET_KEY", "sk_test_xxxxxxxxxxxxxxxx")

# Precios en céntimos (Culqi usa céntimos de sol)
PRICE_SINGLE_REPORT = int(os.getenv("PRICE_SINGLE_REPORT", "990"))     # S/ 9.90
PRICE_DAILY_PASS = int(os.getenv("PRICE_DAILY_PASS", "1990"))          # S/ 19.90
PRICE_MONTHLY_PRO = int(os.getenv("PRICE_MONTHLY_PRO", "4900"))        # S/ 49.00
