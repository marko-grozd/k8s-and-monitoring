import os
import socket
import json
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
import redis.asyncio as aioredis

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/appdb")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
APP_ENV = os.getenv("APP_ENV", "development")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")

# ── Structlog setup ───────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),  # JSON logovi za Loki
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# ── OpenTelemetry setup ───────────────────────────────────────────────────────
def setup_tracing():
    resource = Resource.create({
        "service.name": "k8s-skeleton-backend",
        "service.version": APP_VERSION,
        "deployment.environment": APP_ENV,
    })

    provider = TracerProvider(resource=resource)

    # OTLP exporter (Jaeger, Tempo, ili bilo koji OTel backend)
    otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)

    # Auto-instrumentacija
    AsyncPGInstrumentor().instrument()
    RedisInstrumentor().instrument()

    return trace.get_tracer("k8s-skeleton-backend")

tracer = setup_tracing()

# ── Lifecycle ─────────────────────────────────────────────────────────────────
db_pool = None
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client

    logger.info("startup.begin", env=APP_ENV, version=APP_VERSION)

    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    logger.info("startup.postgres.connected")

    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    logger.info("startup.redis.connected")

    yield

    await db_pool.close()
    await redis_client.aclose()
    logger.info("shutdown.complete")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="K8s Skeleton API", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrike
Instrumentator().instrument(app).expose(app)

# OpenTelemetry FastAPI auto-instrumentacija
FastAPIInstrumentor.instrument_app(app)


# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Bind request context za sve logove u ovom requestu
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        method=request.method,
        path=request.url.path,
        request_id=request.headers.get("x-request-id", "none"),
    )

    logger.info("request.started")
    response = await call_next(request)
    logger.info("request.finished", status_code=response.status_code)

    return response


# ── Schemas ───────────────────────────────────────────────────────────────────
class ItemCreate(BaseModel):
    name: str

class Item(BaseModel):
    id: int
    name: str


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    db_status = "disconnected"
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception:
        pass

    redis_status = "disconnected"
    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception:
        pass

    return {
        "status": "ok",
        "db": db_status,
        "redis": redis_status,
        "hostname": socket.gethostname(),
        "version": APP_VERSION,
        "env": APP_ENV,
    }


@app.get("/api/items", response_model=list[Item])
async def list_items():
    log = logger.bind(endpoint="list_items")

    # Cache check
    cached = await redis_client.get("items:all")
    if cached:
        items = json.loads(cached)
        log.info("cache.hit", count=len(items))
        return items

    # DB query
    with tracer.start_as_current_span("db.fetch_items") as span:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name FROM items ORDER BY id DESC")
        span.set_attribute("db.rows_returned", len(rows))

    items = [{"id": r["id"], "name": r["name"]} for r in rows]

    await redis_client.setex("items:all", 30, json.dumps(items))
    log.info("cache.miss", count=len(items))

    return items


@app.post("/api/items", response_model=Item, status_code=201)
async def create_item(payload: ItemCreate):
    log = logger.bind(endpoint="create_item", name=payload.name)

    if not payload.name.strip():
        log.warning("validation.failed", reason="empty name")
        raise HTTPException(status_code=422, detail="Name cannot be empty")

    with tracer.start_as_current_span("db.create_item") as span:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO items (name) VALUES ($1) RETURNING id, name",
                payload.name.strip()
            )
        span.set_attribute("db.item_id", row["id"])

    await redis_client.delete("items:all")
    log.info("item.created", item_id=row["id"])

    return {"id": row["id"], "name": row["name"]}


@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(item_id: int):
    log = logger.bind(endpoint="delete_item", item_id=item_id)

    with tracer.start_as_current_span("db.delete_item") as span:
        async with db_pool.acquire() as conn:
            result = await conn.execute("DELETE FROM items WHERE id = $1", item_id)
        span.set_attribute("db.item_id", item_id)

    if result == "DELETE 0":
        log.warning("item.not_found", item_id=item_id)
        raise HTTPException(status_code=404, detail="Item not found")

    await redis_client.delete("items:all")
    log.info("item.deleted", item_id=item_id)


@app.get("/")
async def root():
    return {"message": "K8s Skeleton API", "docs": "/docs"}