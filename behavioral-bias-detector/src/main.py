from fastapi import FastAPI

from src.api.routes import router as api_router
from src.config.settings import get_settings
from src.db.session import engine
from src.models.database import Base

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}

