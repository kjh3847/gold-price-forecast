from fastapi import FastAPI
from api.forecast import router as forecast_router
from api.forecast_full import router as forecast_full_router

app = FastAPI(
    title = "Gold Forecast API",
    version = "0.1.0"
)

@app.get("/api/health")
def health():
    return {"status" : "ok"}

app.include_router(forecast_router)
app.include_router(forecast_full_router)