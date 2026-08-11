import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .db import list_sites
from .engine import run_scan
from .brain import run_brain_cycle

logger = logging.getLogger("scrapepilot.scheduler")
scheduler = BackgroundScheduler(daemon=True)

def scheduled(i):
    try:run_scan(i)
    except Exception:pass

def refresh_jobs():
    for j in scheduler.get_jobs():
        if j.id.startswith("site-"):
            scheduler.remove_job(j.id)
    for s in list_sites():
        if s["active"]:
            scheduler.add_job(scheduled,IntervalTrigger(minutes=max(5,int(s["interval_minutes"] or 60))),
                              args=[s["id"]],id=f"site-{s['id']}",replace_existing=True,
                              coalesce=True,max_instances=1)

def start():
    # Schedule the autonomous brain
    # Runs every 8 hours
    scheduler.add_job(
        func=run_brain_cycle,
        trigger=IntervalTrigger(hours=8),
        id="brain_cycle",
        name="Cerebro Autónomo Zero-Touch",
        replace_existing=True,
        misfire_grace_time=3600
    )
    
    if not scheduler.running:
        scheduler.start()
        
    refresh_jobs()
    logger.info("Scheduler started with DB jobs and Autonomous Brain.")
