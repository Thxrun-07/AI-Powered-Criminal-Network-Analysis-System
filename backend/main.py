from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings
from backend.database import db
from backend.services.schema_manager import init_schema
from backend.logging_config import logger
from backend.routers import (
    health_router,
    path_router,
    rankings_router,
    insights_router,
    graph_router,
    cases_router,
    ingest_router,
    events_router,
    blockchain_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application Startup
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode...")
    try:
        # Initialize schema constraints and indexes
        with db.get_session() as session:
            init_schema(session)
    except Exception as e:
        logger.warning(f"Could not connect to Neo4j during startup schema init: {e}")
        logger.info("The application will attempt to connect on subsequent requests.")
    
    yield

    # Application Shutdown
    logger.info("Shutting down application and closing Neo4j connections...")
    db.close()


app = FastAPI(
    title="AI-Powered Criminal Network Analysis System API",
    description="High-performance backend for forensic case ingestion, 10 pattern insight detectors, ambiguity-safe shortest path analysis, and graph centrality rankings.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware (Enabled by default for web & visualization dashboards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount compiled static assets from Vite build if present
dist_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
assets_path = dist_path / "assets"
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

# Global Error Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Request validation failed on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "UnprocessableEntityError",
            "message": "Payload validation failed. Check request schema.",
            "detail": exc.errors()
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected internal server error occurred.",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


# Mount Routers (Specific routes first, parameterized paths after)
app.include_router(health_router)
app.include_router(blockchain_router)
app.include_router(path_router)
app.include_router(rankings_router)
app.include_router(insights_router)
app.include_router(graph_router)
app.include_router(cases_router)
app.include_router(ingest_router)
app.include_router(events_router)


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def serve_dashboard():
    """Serves the interactive Analyst Dashboard UI from frontend/dist or templates/."""
    # Priority 1: Compiled React 19 Vite dist
    if dist_path.exists() and (dist_path / "index.html").exists():
        return (dist_path / "index.html").read_text(encoding="utf-8")
    # Priority 2: Raw frontend/index.html
    frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return frontend_path.read_text(encoding="utf-8")
    # Priority 3: Fallback to embedded template
    template_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "<h1>AI-Powered Criminal Network Analysis System API (Dashboard template not found)</h1>"


@app.head("/", tags=["Dashboard"], include_in_schema=False)
def serve_dashboard_head():
    """Health & load-balancer probe for the root dashboard."""
    return Response(status_code=status.HTTP_200_OK)


