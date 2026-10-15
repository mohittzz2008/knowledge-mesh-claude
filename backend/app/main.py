from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.api.v1.platforms import router as platforms_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.code_artifacts import router as code_artifacts_router
from app.api.v1.knowledge_mesh import router as knowledge_mesh_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.coach import router as coach_router
from app.api.v1.code_lab import router as code_lab_router
from app.api.v1.user import router as user_router

app = FastAPI(title="Knowledge Mesh API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register v1 router endpoints
app.include_router(platforms_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(code_artifacts_router, prefix="/api/v1")
app.include_router(knowledge_mesh_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(coach_router, prefix="/api/v1")
app.include_router(code_lab_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "knowledge-mesh-backend",
    }


@app.get("/db-health")
def db_health_check(db: Session = Depends(get_db)):
    """Verify database connectivity by executing SELECT 1."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )

