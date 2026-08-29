import asyncio
import logging
import random

from fastapi import APIRouter, HTTPException

from metrics import (
    ACTIVE_ORDERS,
    CHAOS_FAIL_RATE,
    CHAOS_LATENCY_MS,
    ORDERS_CREATED,
    ORDERS_FAILED,
    ORDER_VALUE,
)
from models import CHAOS, ORDERS, Order, OrderCreate, new_order_id
from tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=Order, status_code=201)
async def create_order(payload: OrderCreate) -> Order:
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("customer.id", payload.customer_id)
        span.set_attribute("order.item", payload.item)
        span.set_attribute("order.payment_method", payload.payment_method.value)

        ACTIVE_ORDERS.inc()
        try:
            if CHAOS.latency_ms > 0:
                with tracer.start_as_current_span("injected_latency"):
                    await asyncio.sleep(CHAOS.latency_ms / 1000)

            if random.random() < CHAOS.fail_rate:
                ORDERS_FAILED.labels(reason="chaos_injected").inc()
                logger.error(
                    "order_create_failed",
                    extra={
                        "reason": "chaos_injected",
                        "customer_id": payload.customer_id,
                        "fail_rate": CHAOS.fail_rate,
                    },
                )
                span.set_attribute("error", True)
                raise HTTPException(status_code=503, detail="Simulated upstream failure")

            # Simulate a business rule failure
            if payload.item.lower() in {"forbidden", "blocked"}:
                ORDERS_FAILED.labels(reason="item_blocked").inc()
                logger.warning(
                    "order_create_rejected",
                    extra={"reason": "item_blocked", "item": payload.item},
                )
                raise HTTPException(status_code=400, detail="Item is not allowed")

            total = round(payload.quantity * payload.unit_price, 2)
            order = Order(
                id=new_order_id(),
                customer_id=payload.customer_id,
                item=payload.item,
                quantity=payload.quantity,
                unit_price=payload.unit_price,
                total=total,
                payment_method=payload.payment_method,
            )
            ORDERS[order.id] = order

            ORDERS_CREATED.labels(payment_method=payload.payment_method.value).inc()
            ORDER_VALUE.observe(total)
            CHAOS_FAIL_RATE.set(CHAOS.fail_rate)
            CHAOS_LATENCY_MS.set(CHAOS.latency_ms)

            logger.info(
                "order_created",
                extra={
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "total": order.total,
                    "payment_method": order.payment_method.value,
                },
            )
            span.set_attribute("order.id", order.id)
            span.set_attribute("order.total", order.total)
            return order
        finally:
            ACTIVE_ORDERS.dec()


@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: str) -> Order:
    with tracer.start_as_current_span("get_order") as span:
        span.set_attribute("order.id", order_id)
        order = ORDERS.get(order_id)
        if not order:
            logger.warning("order_not_found", extra={"order_id": order_id})
            ORDERS_FAILED.labels(reason="not_found").inc()
            raise HTTPException(status_code=404, detail="Order not found")
        logger.info("order_fetched", extra={"order_id": order_id})
        return order


@router.get("", response_model=list[Order])
async def list_orders() -> list[Order]:
    logger.info("orders_listed", extra={"count": len(ORDERS)})
    return list(ORDERS.values())