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
