"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class IngredientItem(BaseModel):
    """An ingredient line used to make a product"""
    name: str = Field(..., description="Ingredient name, e.g., Espresso, Milk")
    unit: Optional[str] = Field(None, description="Unit label, e.g., g, ml, piece")
    unit_cost: float = Field(0.0, ge=0, description="Cost per unit of the ingredient")
    quantity: float = Field(0.0, ge=0, description="Quantity of unit used for one product")

class Product(BaseModel):
    """
    Coffee shop products (menu items)
    Collection name: "product"
    """
    name: str = Field(..., description="Product name, e.g., Latte 12oz")
    price: float = Field(0.0, ge=0, description="Sell price before tax")
    category: Optional[str] = Field(None, description="Category, e.g., Coffee, Tea, Pastry")
    ingredients: List[IngredientItem] = Field(default_factory=list, description="Breakdown of ingredients used")
    cost: float = Field(0.0, ge=0, description="Computed total cost to make one item (sum of ingredients)")

class Settings(BaseModel):
    """
    App-wide settings
    Collection name: "settings"
    """
    tax_rate: float = Field(0.1, ge=0, description="Sales tax rate as a decimal, e.g., 0.1 for 10%")
