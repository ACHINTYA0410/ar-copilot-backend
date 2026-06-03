from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, checklists, deals, documents, purchase_orders, rules, validation, po_validation
from app.config import settings
from app.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="AR Co-Pilot API",
    description=(
        "AI-powered Accounts Receivable validation platform. "
        "Step B: full backend with mocked AI responses."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

origins = [settings.FRONTEND_URL]
if settings.APP_ENV == "development":
    dev_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]
    for origin in dev_origins:
        if origin not in origins:
            origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(deals.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(validation.router, prefix=API_PREFIX)
app.include_router(rules.router, prefix=API_PREFIX)
app.include_router(checklists.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(purchase_orders.router, prefix=API_PREFIX)
app.include_router(po_validation.router, prefix=f"{API_PREFIX}/po-validation", tags=["po-validation"])
app.include_router(po_validation.router, prefix="/api/po-validation", tags=["po-validation"])



@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
