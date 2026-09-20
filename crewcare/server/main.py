from dotenv import load_dotenv

load_dotenv("whatsapp/.env")

from fastapi import FastAPI
from whatsapp.webhook import router as whatsapp_router

app = FastAPI(title="StationShield")

app.include_router(whatsapp_router)


@app.get("/")
def health():
    return {"status": "ok"}