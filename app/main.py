from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  registers the tables on Base
from app.database import Base, engine
from app.routes import router

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Bulk Certificate Generator", lifespan=lifespan)
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}