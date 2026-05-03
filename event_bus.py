import logging
from typing import Any, Callable, Dict, List

from sqlalchemy.orm import Session

from events import event_to_json
from models import EventLog

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"已注册处理器: {event_type} -> {handler.__name__}")

    def dispatch(self, event: Any, db: Session):
        event_type = event.__class__.__name__

        existing_log = db.query(EventLog).filter(EventLog.event_id == event.event_id).first()
        if existing_log:
            if existing_log.status == "completed":
                logger.info(f"事件已处理, 幂等跳过: event_id={event.event_id}, type={event_type}")
                return
            if existing_log.status == "failed":
                logger.info(f"事件之前失败, 允许重试: event_id={event.event_id}, type={event_type}")
                existing_log.status = "pending"
                db.flush()
        else:
            payload = event_to_json(event)
            event_log = EventLog(
                event_id=event.event_id,
                event_type=event_type,
                payload=payload,
                status="pending",
            )
            db.add(event_log)
            db.flush()

        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.warning(f"事件 {event_type} 没有注册的处理器")
            return

        all_success = True
        for handler in handlers:
            try:
                handler(event, db)
            except Exception as e:
                all_success = False
                logger.error(f"处理器 {handler.__name__} 处理事件 {event_type} 失败: {e}")
                db.rollback()
                self._update_event_log_status(db, event.event_id, "failed")
                return

        if all_success:
            self._update_event_log_status(db, event.event_id, "completed")

    def _update_event_log_status(self, db: Session, event_id: str, status: str):
        log_entry = db.query(EventLog).filter(EventLog.event_id == event_id).first()
        if log_entry:
            log_entry.status = status
            db.flush()


event_bus = EventBus()
