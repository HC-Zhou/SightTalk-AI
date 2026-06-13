from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sighttalk_api.api.v1.health import health, router as health_router


app = FastAPI(title="SightTalk AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)

# Keep a short health endpoint for local smoke checks and the original plan.
app.get("/health", tags=["health"])(health)


def run() -> None:
    import uvicorn

    uvicorn.run("sighttalk_api.main:app", host="127.0.0.1", port=8000, reload=True)

