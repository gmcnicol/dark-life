from fastapi import FastAPI

app = FastAPI(title="Dark Life API")


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
