from sqlalchemy import Column, Integer, String
from  database import Base
class OrderTracking(Base):
    __tablename__ = "order_tracking"

    order_id = Column(Integer, primary_key=True, index=True)
    status = Column(String)
