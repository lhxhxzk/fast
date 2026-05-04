import logging
import time
from uuid import uuid4

import requests as http_requests
from sqlalchemy.orm import Session

from event_bus import event_bus
from events import OrderCreatedEvent, ProductionTaskCreatedEvent, PurchaseNeededEvent
from models import Inventory, ProductionTask

logger = logging.getLogger(__name__)

INVENTORY_SERVICE_URL = "http://127.0.0.1:9999/inventory"


def call_inventory_service(quantity: int) -> bool:
    try:
        resp = http_requests.get(INVENTORY_SERVICE_URL, timeout=2)
        return resp.status_code == 200
    except (http_requests.exceptions.ConnectionError,
            http_requests.exceptions.Timeout,
            http_requests.exceptions.RequestException) as e:
        raise ConnectionError(f"网络服务不可用: {e}")


def handle_order_created(event: OrderCreatedEvent, db: Session):
    existing = db.query(ProductionTask).filter(
        ProductionTask.event_id == event.event_id
    ).first()
    if existing:
        logger.info(f"幂等跳过: ProductionTask 已存在, event_id={event.event_id}")
        return

    if event.product_name == "SLOW":
        logger.info(f"模拟超时: product_name=SLOW, 等待5秒...")
        time.sleep(5)

    if event.product_name == "NETFAIL":
        logger.info(f"模拟网络失败: product_name=NETFAIL, 调用不存在的库存服务...")
        call_inventory_service(event.quantity)

    inventory = db.query(Inventory).filter(Inventory.product_name == event.product_name).first()
    if not inventory:
        raise ValueError(f"产品不存在: {event.product_name}")
    if event.quantity <= 0:
        raise ValueError(f"数量必须大于0: quantity={event.quantity}")
    if inventory.quantity < event.quantity:
        raise ValueError(f"库存不足，无法创建生产任务: 当前库存={inventory.quantity}, 需求={event.quantity}")

    inventory.quantity -= event.quantity
    db.flush()

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
