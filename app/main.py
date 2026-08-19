from fastapi import FastAPI

app = FastAPI(title="Extraction Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Confirm that the API process is available."""
    return {"status": "ok"}
