import logging

from fastapi import APIRouter

from metrics import CHAOS_FAIL_RATE, CHAOS_LATENCY_MS
from models import CHAOS, ChaosConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chaos", tags=["chaos"])


@router.get("")
async def get_chaos() -> ChaosConfig:
    return CHAOS


@router.post("")
async def set_chaos(config: ChaosConfig) -> ChaosConfig:
    """Inject failures and latency so you can watch dashboards react."""
    CHAOS.fail_rate = config.fail_rate
    CHAOS.latency_ms = config.latency_ms
    CHAOS_FAIL_RATE.set(CHAOS.fail_rate)
    CHAOS_LATENCY_MS.set(CHAOS.latency_ms)
    logger.warning(
        "chaos_config_updated",
        extra={"fail_rate": CHAOS.fail_rate, "latency_ms": CHAOS.latency_ms},
    )
    return CHAOS


@router.post("/reset")
async def reset_chaos() -> ChaosConfig:
    CHAOS.fail_rate = 0.0
    CHAOS.latency_ms = 0
    CHAOS_FAIL_RATE.set(0)
    CHAOS_LATENCY_MS.set(0)
    logger.info("chaos_config_reset")
    return CHAOS


@router.get("/boom")
async def boom():
    """Always raises — useful to generate 500s and error traces/logs instantly."""
    logger.error("intentional_boom", extra={"reason": "chaos_boom_endpoint"})
    raise RuntimeError("Intentional boom for observability practice")