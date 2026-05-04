from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class OrderCreateRequest(BaseModel):
    order_id: str
    product_name: str
    quantity: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    product_name: str
    quantity: int
    status: str


class OrderListItem(BaseModel):
    order_id: str
    product_name: str
    quantity: int
    status: str
    created_at: Optional[str] = None


class EventListItem(BaseModel):
    event_id: str
    event_type: str
    status: str
    order_id: Optional[str] = None
    created_at: Optional[str] = None


class OrderListResponse(BaseModel):
    orders: List[OrderListItem]


class EventListResponse(BaseModel):
    events: List[EventListItem]


class InventoryListItem(BaseModel):
    product_name: str
    quantity: int


class InventoryListResponse(BaseModel):
    inventory: List[InventoryListItem]
