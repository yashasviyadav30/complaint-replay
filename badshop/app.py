"""BadShop: a tiny store that plays "the customer's app".

The code in this folder is bug-free. Bugs are injected into a working copy by
replay/bugs.py, so Complaint Replay can find and fix them like a real repo.
"""

import asyncio
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

STATIC_DIR = Path(__file__).parent / "static"
DEMO_OTP = "123456"
SMS_GATEWAY_DELAY_S = 2.5  # a real SMS gateway is slow; fine on fast networks
COUPONS = {"SAVE10": 0.10}
PRODUCTS = [
    {"id": 1, "name": "Masala Chai", "name_hi": "मसाला चाय", "price": 120},
    {"id": 2, "name": "Basmati Rice 1kg", "name_hi": "बासमती चावल 1kg", "price": 180},
    {"id": 3, "name": "Mango Pickle", "name_hi": "आम का अचार", "price": 150},
    {"id": 4, "name": "Steel Tiffin", "name_hi": "स्टील टिफ़िन", "price": 150},
]
PRICES = {p["id"]: p["price"] for p in PRODUCTS}

app = FastAPI(title="BadShop")


class OtpSend(BaseModel):
    phone: str


class OtpVerify(BaseModel):
    phone: str
    otp: str


class CartItem(BaseModel):
    id: int
    qty: int = Field(gt=0, le=20)


class Cart(BaseModel):
    items: list[CartItem]
    coupon: str | None = None


def price(items: list[CartItem], coupon: str | None) -> tuple[int, int, int]:
    unknown = [i.id for i in items if i.id not in PRICES]
    if unknown:
        raise HTTPException(400, {"error": "unknown_product", "ids": unknown})
    subtotal = sum(PRICES[i.id] * i.qty for i in items)
    discount = round(subtotal * COUPONS.get((coupon or "").upper(), 0))
    return subtotal, discount, subtotal - discount


def check_phone(phone: str) -> None:
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        raise HTTPException(400, {"error": "invalid_phone"})


@app.get("/api/products")
def products():
    return PRODUCTS


@app.post("/api/otp/send")
async def otp_send(req: OtpSend):
    check_phone(req.phone)
    await asyncio.sleep(SMS_GATEWAY_DELAY_S)
    return {"sent": True, "demo_otp": DEMO_OTP}


@app.post("/api/otp/verify")
def otp_verify(req: OtpVerify):
    check_phone(req.phone)
    if req.otp != DEMO_OTP:
        raise HTTPException(400, {"error": "invalid_otp"})
    return {"ok": True}


@app.post("/api/cart/quote")
def quote(cart: Cart):
    subtotal, discount, total = price(cart.items, cart.coupon)
    return {"subtotal": subtotal, "discount": discount, "total": total}


@app.post("/api/checkout")
def checkout(cart: Cart):
    if not cart.items:
        raise HTTPException(400, {"error": "empty_cart"})
    subtotal, discount, total = price(cart.items, cart.coupon)
    return {"order_id": "BS-1042", "charged": total}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
