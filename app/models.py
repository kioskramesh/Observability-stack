from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class PaymentMethod(str, Enum):
    card = "card"
    upi = "upi"
    wallet = "wallet"


class OrderCreate(BaseModel):
    customer_id: str = Field(..., examples=["cust-42"])
    item: str = Field(..., examples=["wireless-headphones"])
    quantity: int = Field(..., ge=1, le=100, examples=[1])
    unit_price: float = Field(..., gt=0, examples=[79.99])
    payment_method: PaymentMethod = PaymentMethod.card


class Order(BaseModel):
    id: str
    customer_id: str
    item: str
    quantity: int
    unit_price: float
    total: float
    payment_method: PaymentMethod
    status: str = "confirmed"


class ChaosConfig(BaseModel):
    fail_rate: float = Field(0.0, ge=0.0, le=1.0)
    latency_ms: int = Field(0, ge=0, le=30000)


def new_order_id() -> str:
    return f"ord-{uuid4().hex[:8]}"


# In-memory store — fine for a local observability lab
ORDERS: dict[str, Order] = {}
CHAOS = ChaosConfig()


def get_order(order_id: str) -> Optional[Order]:
    return ORDERS.get(order_id)