import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from event_bus import event_bus
from events import OrderCreatedEvent, ProductionTaskCreatedEvent, PurchaseNeededEvent
from models import ProductionTask

logger = logging.getLogger(__name__)


def handle_order_created(event: OrderCreatedEvent, db: Session):
    existing = db.query(ProductionTask).filter(
        ProductionTask.event_id == event.event_id
    ).first()
    if existing:
        logger.info(f"幂等跳过: ProductionTask 已存在, event_id={event.event_id}")
        return

    if event.quantity <= 0:
        raise ValueError(f"库存不足，无法创建生产任务: quantity={event.quantity}")

    task_id = str(uuid4())
    task = ProductionTask(
        task_id=task_id,
        order_id=event.order_id,
        product_name=event.product_name,
        quantity=event.quantity,
        event_id=event.event_id,
    )
    db.add(task)
    db.flush()

    new_event = ProductionTaskCreatedEvent(
        task_id=task_id,
        order_id=event.order_id,
        product_name=event.product_name,
        quantity=event.quantity,
    )
    logger.info(f"生产任务已创建: task_id={task_id}, order_id={event.order_id}")
    event_bus.dispatch(new_event, db)


def handle_production_task_created(event: ProductionTaskCreatedEvent, db: Session):
    if event.quantity > 10:
        purchase_id = str(uuid4())
        new_event = PurchaseNeededEvent(
            purchase_id=purchase_id,
            order_id=event.order_id,
            material_name=event.product_name,
            quantity_needed=event.quantity,
        )
        logger.info(f"数量>10, 触发采购需求: purchase_id={purchase_id}")
        event_bus.dispatch(new_event, db)
    else:
        logger.info(f"生产任务创建完成, 数量<=10, 无需采购: task_id={event.task_id}")


def handle_purchase_needed(event: PurchaseNeededEvent, db: Session):
    logger.info(
        f"采购需求已记录: material_name={event.material_name}, "
        f"quantity_needed={event.quantity_needed}, purchase_id={event.purchase_id}"
    )
