import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from uuid import uuid4


@dataclass
class OrderCreatedEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    product_name: str = ""
    quantity: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ProductionTaskCreatedEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    task_id: str = ""
    order_id: str = ""
    product_name: str = ""
    quantity: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PurchaseNeededEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    purchase_id: str = ""
    order_id: str = ""
    material_name: str = ""
    quantity_needed: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def event_to_json(event) -> str:
    return json.dumps(asdict(event), ensure_ascii=False)
