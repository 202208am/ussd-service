
from fastapi import FastAPI
from pydantic import BaseModel
from app.ussd import handle_ussd

app = FastAPI(title="INAI USSD Service")


class USSDRequest(BaseModel):
    msisdn: str
    session_id: str
    input: str


@app.get("/")
def home():
    return {"status": "running"}


@app.post("/ussd")
def ussd(request: USSDRequest):
    return handle_ussd(
        msisdn=request.msisdn,
        session_id=request.session_id,
        user_input=request.input
    )
