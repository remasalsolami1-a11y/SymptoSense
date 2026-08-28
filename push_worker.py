"""Always-on Railway worker for backend-driven medication Web Push."""
import logging
import os
import signal
import time

import medication_push

logging.basicConfig(level=os.environ.get("LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log=logging.getLogger("SymptoSense.PushWorker")
running=True

def stop(*_):
    global running; running=False

signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)


def main():
    medication_push.init_schema()
    interval=max(15,min(60,int(os.environ.get("PUSH_WORKER_INTERVAL_SECONDS","20"))))
    log.info("Medication push worker started (interval=%ss, configured=%s)",interval,medication_push.push_config()["configured"])
    while running:
        started=time.time()
        try:
            stats=medication_push.send_due_notifications()
            if stats.get("sent") or stats.get("failed"): log.info("push cycle: %s",stats)
        except Exception as exc:
            log.exception("push cycle failed: %s",type(exc).__name__)
        delay=max(1,interval-(time.time()-started)); time.sleep(delay)
    log.info("Medication push worker stopped")

if __name__=="__main__": main()
