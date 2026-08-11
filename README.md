# ScrapePilot PRO v2

MVP funcional para convertir el concepto de scraping en un sistema de monitoreo automatizado.

Incluye:
- dashboard web;
- SQLite;
- API REST;
- monitoreo automático con scheduler;
- intervalos configurables;
- extracción de precios;
- selector CSS opcional;
- detección de cambios;
- dirección del cambio de precio;
- scoring de oportunidad;
- historial;
- exportación CSV;
- alertas Telegram opcionales;
- logs de ejecuciones.

No intenta saltarse CAPTCHA, autenticación, paywalls, anti-bot o restricciones. Usa solo fuentes cuyo acceso automatizado esté permitido y respeta sus reglas.

## Ejecutar en Windows

Doble clic en `run_windows.bat`, o:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Abrir http://127.0.0.1:8000

## Ejemplo

Registra una URL pública permitida. Si tiene un precio en `.price`, coloca `.price` como selector. El sistema podrá revisarla cada 5, 10, 30, 60 minutos, etc.

## Modelo comercial

El software es una base. Para monetizarlo debemos convertir una función en una solución concreta que un negocio necesite, por ejemplo monitoreo de precios/competencia y alertas.

No hay garantía de ingresos: la validación comercial viene después de encontrar clientes que paguen.
