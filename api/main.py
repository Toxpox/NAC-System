from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="NAC Policy Engine")

# --- 1. AUTHENTICATION (Kimlik Dogrulama) ---
class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/auth")
async def authenticate(req: AuthRequest):
    # Geçici --  veritabanı entegrasyonu bir sonraki adımda eklenecek
    if req.username == "admin" and req.password == "Password123!":
        return {"status": "accept", "type": "pap"}
    
    return {"status": "reject"}


# --- 2. AUTHORIZATION (Yetkilendirme ve VLAN) ---
class AuthorizeRequest(BaseModel):
    username: str

@app.post("/authorize")
async def authorize(req: AuthorizeRequest):
    return {
        "reply:Tunnel-Type": {"type": "integer", "value": [13]},
        "reply:Tunnel-Medium-Type": {"type": "integer", "value": [6]},
        "reply:Tunnel-Private-Group-Id": {"type": "string", "value": ["10"]}
    }


# --- 3. ACCOUNTING (Oturum / Kota Loglari) ---
@app.post("/accounting")
async def accounting(req: dict):
    print("REST Accounting Paketi Geldi:", req)
    return {"status": "ok"}


# --- Diger Radius Ekstralari ---
@app.post("/post-auth")
async def post_auth(req: dict):
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
