import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import SessionLocal, get_db, init_db
from event_bus import event_bus
from events import OrderCreatedEvent
from handlers import handle_order_created, handle_production_task_created, handle_purchase_needed
from models import EventLog, Order
from schemas import OrderCreateRequest, OrderResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    event_bus.subscribe("OrderCreatedEvent", handle_order_created)
    event_bus.subscribe("ProductionTaskCreatedEvent", handle_production_task_created)
    event_bus.subscribe("PurchaseNeededEvent", handle_purchase_needed)
    logger.info("所有事件处理器注册成功")
    yield


app = FastAPI(title="Event-Driven Manufacturing", lifespan=lifespan)


@app.get("/")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return {"status": "error", "db": "disconnected"}


@app.post("/orders", response_model=OrderResponse, status_code=202)
def create_order(
    request: OrderCreateRequest,
    background_tasks: BackgroundTasks,
):
    db = SessionLocal()
    try:
        existing = db.query(Order).filter(Order.order_id == request.order_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="order already exists")

        order = Order(
            order_id=request.order_id,
            product_name=request.product_name,
            quantity=request.quantity,
        )
        db.add(order)

        event = OrderCreatedEvent(
            order_id=request.order_id,
            product_name=request.product_name,
            quantity=request.quantity,
        )
        payload = event.to_json()

        event_log = EventLog(
            event_id=event.event_id,
            event_type=event.__class__.__name__,
            payload=payload,
            status="pending",
        )
        db.add(event_log)
        db.commit()

        background_tasks.add_task(process_event_log, event_log.id, event)

        return OrderResponse(
            order_id=order.order_id,
            product_name=order.product_name,
            quantity=order.quantity,
            status="pending processing",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建订单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


async def process_event_log(event_log_id: int, event):
    db = SessionLocal()
    try:
        log_entry = db.query(EventLog).filter(EventLog.id == event_log_id).first()
        if not log_entry:
            logger.error(f"事件日志不存在: id={event_log_id}")
            return
        if log_entry.status != "pending":
            logger.info(f"事件已处理, 跳过: id={event_log_id}, status={log_entry.status}")
            return

        event_bus.dispatch(event, db)
        db.commit()
    except Exception as e:
        logger.error(f"后台处理事件失败: {e}")
        try:
            db.rollback()
            log_entry = db.query(EventLog).filter(EventLog.id == event_log_id).first()
            if log_entry and log_entry.status == "pending":
                log_entry.status = "failed"
                db.commit()
        except Exception as rollback_err:
            logger.error(f"回滚后更新状态也失败: {rollback_err}")
            db.rollback()
    finally:
        db.close()
