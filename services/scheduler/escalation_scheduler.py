from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import STATE_RUNNING

from services.escalation.escalation_service import (
    EscalationService
)

scheduler = BackgroundScheduler()


def start_escalation_scheduler():

    if scheduler.state == STATE_RUNNING:
        print("Scheduler already running")
        return

    scheduler.add_job(
        EscalationService.run_escalation_process,
        'interval',
        seconds=30,
        id='escalation_job',
        replace_existing=True
    )

    scheduler.start()

    print("Escalation Scheduler Started")