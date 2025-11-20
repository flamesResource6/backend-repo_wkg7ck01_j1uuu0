import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from database import db, create_document, get_documents
from bson import ObjectId
from schemas import Product as ProductSchema, Settings as SettingsSchema, IngredientItem as IngredientSchema

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


class IngredientIn(BaseModel):
    name: str
    unit: Optional[str] = None
    unit_cost: float
    quantity: float

class ProductIn(BaseModel):
    name: str
    price: float
    category: Optional[str] = None
    ingredients: List[IngredientIn] = []

class ProductOut(BaseModel):
    id: str
    name: str
    category: Optional[str]
    price: float
    cost: float
    margin_amount: float
    margin_percent: float
    ingredients: List[IngredientIn]

class SettingsIn(BaseModel):
    tax_rate: float

class SettingsOut(SettingsIn):
    id: Optional[str] = None


def compute_cost(ingredients: List[IngredientIn]) -> float:
    return float(sum((i.unit_cost or 0) * (i.quantity or 0) for i in ingredients))


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
            {
                "name": "Espresso",
                "category": "Coffee",
                "price": 3.0,
                "ingredients": [
                    {"name": "Coffee Beans", "unit": "g", "unit_cost": 0.02, "quantity": 18},
                    {"name": "Cup", "unit": "pc", "unit_cost": 0.12, "quantity": 1},
                ],
            },
            {
                "name": "Latte 12oz",
                "category": "Coffee",
                "price": 4.5,
                "ingredients": [
                    {"name": "Coffee Beans", "unit": "g", "unit_cost": 0.02, "quantity": 18},
                    {"name": "Milk", "unit": "ml", "unit_cost": 0.001, "quantity": 220},
                    {"name": "Cup", "unit": "pc", "unit_cost": 0.12, "quantity": 1},
                ],
            },
        ]
        result = []
        for i, x in enumerate(sample):
            ings = [IngredientIn(**ing) for ing in x.get("ingredients", [])]
            cost = compute_cost(ings)
            price = float(x.get("price", 0))
            margin_amount = price - cost
            margin_percent = (margin_amount / price * 100) if price else 0
            result.append(
                ProductOut(
                    id=str(i),
                    name=x["name"],
                    category=x.get("category"),
                    price=price,
                    cost=cost,
                    margin_amount=margin_amount,
                    margin_percent=margin_percent,
                    ingredients=ings,
                )
            )
        return result

    items = get_documents("product")
    result = []
    for d in items:
        s = serialize_doc(d)
        ings = [IngredientIn(**ing) for ing in s.get("ingredients", [])]
        price = float(s.get("price", 0))
        cost = compute_cost(ings)
        margin_amount = price - cost
        margin_percent = (margin_amount / price * 100) if price else 0
        result.append(
            ProductOut(
                id=s["id"],
                name=s.get("name"),
                category=s.get("category"),
                price=price,
                cost=cost,
                margin_amount=margin_amount,
                margin_percent=margin_percent,
                ingredients=ings,
            )
        )
    return result


@app.post("/api/products", response_model=ProductOut)
def create_product(payload: ProductIn):
    ings = [IngredientIn(**ing.model_dump()) for ing in payload.ingredients]
    cost = compute_cost(ings)
    if db is None:
        price = float(payload.price)
        margin_amount = price - cost
        margin_percent = (margin_amount / price * 100) if price else 0
        return ProductOut(
            id="temp",
            name=payload.name,
            category=payload.category,
            price=price,
            cost=cost,
            margin_amount=margin_amount,
            margin_percent=margin_percent,
            ingredients=ings,
        )
    # Persist
    to_insert = {
        "name": payload.name,
        "category": payload.category,
        "price": float(payload.price),
        "ingredients": [ing.model_dump() for ing in ings],
        # store cost as well for convenience
        "cost": cost,
    }
    _id = create_document("product", to_insert)
    d = db["product"].find_one({"_id": ObjectId(_id)})
    s = serialize_doc(d)
    ings_db = [IngredientIn(**ing) for ing in s.get("ingredients", [])]
    price = float(s.get("price", 0))
    cost = compute_cost(ings_db)
    margin_amount = price - cost
    margin_percent = (margin_amount / price * 100) if price else 0
    return ProductOut(
        id=s["id"],
        name=s.get("name"),
        category=s.get("category"),
        price=price,
        cost=cost,
        margin_amount=margin_amount,
        margin_percent=margin_percent,
        ingredients=ings_db,
    )


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
