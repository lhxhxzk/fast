from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class OrderCreatedEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    product_name: str
    quantity: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProductionTaskCreatedEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    order_id: str
    product_name: str
    quantity: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PurchaseNeededEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    purchase_id: str
    material_name: str
    quantity_needed: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
