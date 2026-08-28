from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self):
        self._scheduler: Optional[BackgroundScheduler] = None
        self._is_running = False
    
    def _get_scheduler(self) -> BackgroundScheduler:
        if self._scheduler is None:
            jobstores = {
                'default': SQLAlchemyJobStore(url='sqlite:///scheduler_jobs.db')
            }
            self._scheduler = BackgroundScheduler(jobstores=jobstores)
        return self._scheduler
    
    def start(self) -> None:
        if not self._is_running:
            self._scheduler.start()
            self._is_running = True
            logger.info("Scheduler started")
    
    def stop(self) -> None:
        if self._is_running and self._scheduler:
            self._scheduler.shutdown()
            self._is_running = False
            logger.info("Scheduler stopped")
    
    def add_job(self, job_id: str, func: Callable, trigger: str, **kwargs) -> None:
        scheduler = self._get_scheduler()
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        if trigger.upper() == "DAILY":
            scheduler.add_job(func, CronTrigger(hour=3, minute=0), id=job_id, **kwargs)
        elif trigger.upper() == "HOURLY":
            scheduler.add_job(func, IntervalTrigger(hours=1), id=job_id, **kwargs)
        else:
            raise ValueError(f"Unsupported trigger: {trigger}")
        logger.info(f"Job '{job_id}' scheduled with trigger '{trigger}'")
    
    def remove_job(self, job_id: str) -> None:
        scheduler = self._get_scheduler()
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"Job '{job_id}' removed")

scheduler_manager = SchedulerManager()