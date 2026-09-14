from app.schemas import TelemetryInput, TelemetryResponse
from datetime import datetime, timezone
from fastapi import FastAPI
import logfire

app = FastAPI()

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_fastapi(app)

@app.get("/")
async def root():
    return {"message" : "Hello World"}

@app.get("/health")
async def health():
    return {"status" : "ok"}

drivers_state: dict[str, TelemetryInput] = {}

@app.post("/telemetry", response_model=TelemetryResponse) 
async def receive_telemetry(data: TelemetryInput):
    drivers_state[data.driver_id] = data
    return TelemetryResponse(status="ok", processed_at=datetime.now(timezone.utc))

@app.get("/drivers")
async def list_drivers():
    return drivers_state
