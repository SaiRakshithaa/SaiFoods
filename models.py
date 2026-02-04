from sqlalchemy import Column, Integer, String, Float, ForeignKey
from database import Base


class OrderTracking(Base):
    __tablename__ = "order_tracking"

    order_id = Column(Integer, primary_key=True, autoincrement=False)
    status = Column(String(50))


class FoodItem(Base):
    __tablename__ = "food_items"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    price = Column(Float, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, autoincrement=False)
    item_id = Column(Integer, ForeignKey("food_items.item_id"), primary_key=True)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)