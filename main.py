import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from database import db, create_document, get_documents
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to convert Mongo docs to JSON-serializable

def serialize_doc(doc):
    if not doc:
        return doc
    doc["id"] = str(doc.get("_id"))
    doc.pop("_id", None)
    # Convert datetimes to isoformat
    for k, v in list(doc.items()):
        import datetime
        if isinstance(v, (datetime.datetime, datetime.date)):
            doc[k] = v.isoformat()
    return doc


class ProductIn(BaseModel):
    name: str
    cost: float
    price: float
    category: Optional[str] = None

class ProductOut(ProductIn):
    id: str
    margin_amount: float
    margin_percent: float

class SettingsIn(BaseModel):
    tax_rate: float

class SettingsOut(SettingsIn):
    id: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Coffee Shop Backend Running"}


@app.get("/api/settings", response_model=SettingsOut)
def get_settings():
    if db is None:
        # Provide default if no DB configured
        return SettingsOut(tax_rate=0.1)
    doc = db["settings"].find_one({})
    if not doc:
        # default create
        create_document("settings", {"tax_rate": 0.1})
        doc = db["settings"].find_one({})
    s = serialize_doc(doc)
    return SettingsOut(id=s.get("id"), tax_rate=s.get("tax_rate", 0.1))


@app.put("/api/settings", response_model=SettingsOut)
def update_settings(payload: SettingsIn):
    if db is None:
        return SettingsOut(tax_rate=payload.tax_rate)
    existing = db["settings"].find_one({})
    if existing:
        db["settings"].update_one({"_id": existing["_id"]}, {"$set": {"tax_rate": payload.tax_rate}})
        doc = db["settings"].find_one({"_id": existing["_id"]})
    else:
        create_document("settings", {"tax_rate": payload.tax_rate})
        doc = db["settings"].find_one({})
    s = serialize_doc(doc)
    return SettingsOut(id=s.get("id"), tax_rate=s.get("tax_rate", 0.1))


@app.get("/api/products", response_model=List[ProductOut])
def list_products():
    if db is None:
        # stateless default sample list
        sample = [
            {"name": "Espresso", "cost": 0.6, "price": 3.0, "category": "Coffee"},
            {"name": "Latte 12oz", "cost": 1.1, "price": 4.5, "category": "Coffee"},
            {"name": "Croissant", "cost": 1.2, "price": 3.5, "category": "Pastry"},
        ]
        return [ProductOut(**x, id=str(i), margin_amount=x["price"]-x["cost"], margin_percent=((x["price"]-x["cost"]) / x["price"]*100 if x["price"] else 0)) for i, x in enumerate(sample)]

    items = get_documents("product")
    result = []
    for d in items:
        s = serialize_doc(d)
        margin_amount = float(s.get("price", 0)) - float(s.get("cost", 0))
        margin_percent = (margin_amount / float(s.get("price", 1))) * 100 if float(s.get("price", 0)) else 0
        result.append(ProductOut(id=s["id"], name=s.get("name"), cost=float(s.get("cost", 0)), price=float(s.get("price", 0)), category=s.get("category"), margin_amount=margin_amount, margin_percent=margin_percent))
    return result


@app.post("/api/products", response_model=ProductOut)
def create_product(payload: ProductIn):
    if db is None:
        # No persistence available
        x = payload.model_dump()
        margin_amount = x["price"] - x["cost"]
        margin_percent = (margin_amount / x["price"] * 100) if x["price"] else 0
        return ProductOut(id="temp", **x, margin_amount=margin_amount, margin_percent=margin_percent)
    _id = create_document("product", payload)
    d = db["product"].find_one({"_id": ObjectId(_id)})
    s = serialize_doc(d)
    margin_amount = float(s.get("price", 0)) - float(s.get("cost", 0))
    margin_percent = (margin_amount / float(s.get("price", 1))) * 100 if float(s.get("price", 0)) else 0
    return ProductOut(id=s["id"], name=s.get("name"), cost=float(s.get("cost", 0)), price=float(s.get("price", 0)), category=s.get("category"), margin_amount=margin_amount, margin_percent=margin_percent)


@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    if db is None:
        return {"ok": True}
    try:
        db["product"].delete_one({"_id": ObjectId(product_id)})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available" if db is None else "✅ Connected & Working",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "collections": []
    }
    try:
        if db is not None:
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
