from prometheus_client import Counter, Gauge, Histogram

# Business / custom metrics (in addition to HTTP ones from the instrumentator)
ORDERS_CREATED = Counter(
    "orders_created_total",
    "Total number of orders successfully created",
    ["payment_method"],
)

ORDERS_FAILED = Counter(
    "orders_failed_total",
    "Total number of failed order attempts",
    ["reason"],
)

ORDER_VALUE = Histogram(
    "order_value_dollars",
    "Order total value in dollars",
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000),
)

ACTIVE_ORDERS = Gauge(
    "orders_in_progress",
    "Orders currently being processed",
)

CHAOS_FAIL_RATE = Gauge(
    "chaos_fail_rate",
    "Current injected failure rate (0-1)",
)

CHAOS_LATENCY_MS = Gauge(
    "chaos_latency_ms",
    "Current injected latency in milliseconds",
)