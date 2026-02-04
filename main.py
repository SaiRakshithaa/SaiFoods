from fastapi import FastAPI, Depends, HTTPException, Request
from typing import Dict, Any
from sqlalchemy.orm import Session
from database import SessionLocal
from models import OrderTracking, FoodItem, Order
from sqlalchemy import func
import re
import json

app = FastAPI()
orders = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def extract_session_id(output_contexts):
    if not output_contexts:
        return None
    context_name = output_contexts[0]["name"]
    parts = context_name.split("/")
    if "sessions" in parts:
        session_index = parts.index("sessions")
        return parts[session_index + 1]
    return None


def format_order_summary(order_dict):
    items = []

    for item, qty in order_dict.items():
        items.append(f"{qty} {item}")

    if len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return " and ".join(items)
    else:
        return ", ".join(items[:-1]) + " and " + items[-1]


def handle_order_add(parameters: Dict[str, Any], session_id: str):
    items = parameters.get("food-items", [])
    quantities = parameters.get("number", [])

    # Convert quantities to int
    quantities = [int(q) for q in quantities]

    if session_id not in orders:
        orders[session_id] = {}

    for item, qty in zip(items, quantities):
        if item in orders[session_id]:
            orders[session_id][item] += qty
        else:
            orders[session_id][item] = qty

    print("CURRENT ORDERS:", orders)

    order_summary = format_order_summary(orders[session_id])

    return {
        "fulfillmentText": f"So far you have {order_summary}. Do you need anything else?"
    }


def handle_order_remove(parameters: Dict[str, Any], session_id: str):
    items = parameters.get("food-items", [])
    quantities = parameters.get("number", [])

    if session_id not in orders:
        return {
            "fulfillmentText": "You don't have any items in your cart."
        }

    # Convert quantities to int
    quantities = [int(q) for q in quantities]

    removed_items = []
    for item, qty in zip(items, quantities):
        if item in orders[session_id]:
            orders[session_id][item] -= qty
            if orders[session_id][item] <= 0:
                del orders[session_id][item]
            removed_items.append(f"{qty} {item}")

    if not orders[session_id]:
        del orders[session_id]
        return {
            "fulfillmentText": "Your cart is now empty. What would you like to order?"
        }

    order_summary = format_order_summary(orders[session_id])
    return {
        "fulfillmentText": f"Removed {', '.join(removed_items)}. You still have {order_summary}."
    }


def handle_order_id(parameters: dict, session_id: str, db):
    # Extract order_id safely
    order_param = parameters.get("number")

    if isinstance(order_param, list):
        order_id = int(order_param[0])
    else:
        order_id = int(order_param)

    # Query DB
    order = db.query(OrderTracking) \
        .filter(OrderTracking.order_id == order_id) \
        .first()

    if not order:
        return {
            "fulfillmentText": f"I couldn't find any order with ID {order_id}."
        }

    return {
        "fulfillmentText": f"Your order {order_id} is currently {order.status}."
    }


def calculate_total_price(price: float, quantity: int) -> float:
    return price * quantity


def generate_new_order_id(db):
    max_order_id = db.query(func.max(Order.order_id)).scalar()
    return (max_order_id or 0) + 1


def finish_order(parameters: dict, session_id: str, db):
    print("Finishing order for session:", session_id)
    print("Current orders:", orders)

    if session_id not in orders:
        return {
            "fulfillmentText": "You don't have any active order."
        }

    order_items = orders[session_id]

    # Generate order_id
    new_order_id = generate_new_order_id(db)

    # Process each food item
    total_order_price = 0

    for item_name, quantity in order_items.items():
        food_item = db.query(FoodItem).filter(
            FoodItem.name.ilike(item_name)
        ).first()

        if not food_item:
            return {
                "fulfillmentText": f"Sorry, {item_name} is not available in our menu."
            }

        total_price = calculate_total_price(food_item.price, quantity)
        total_order_price += total_price

        # Check if this combination already exists
        existing = db.query(Order).filter(
            Order.order_id == new_order_id,
            Order.item_id == food_item.item_id
        ).first()

        if existing:
            existing.quantity += quantity
            existing.total_price += total_price
        else:
            # FIX: Remove the duplicate db.add() - just create and add once
            order_row = Order(
                order_id=new_order_id,
                item_id=food_item.item_id,
                quantity=quantity,
                total_price=total_price
            )
            db.add(order_row)

    # Add tracking entry
    tracking = OrderTracking(
        order_id=new_order_id,
        status="in transit"
    )
    db.add(tracking)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
        return {
            "fulfillmentText": "Sorry, there was an error placing your order. Please try again."
        }

    # Clear the session order
    del orders[session_id]

    return {
        "fulfillmentText": f"Your order has been placed successfully. Your order ID is {new_order_id}. Total: ₹{total_order_price:.2f}"
    }


@app.post("/")
async def dialogflow_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()

        query_result = body.get("queryResult", {})

        intent_name = query_result.get("intent", {}).get("displayName")
        print(intent_name)
        parameters = query_result.get("parameters", {})
        output_contexts = query_result.get("outputContexts", [])

        session_id = extract_session_id(output_contexts)
        print("Session ID:", session_id)

        # Intent routing
        if intent_name == "order.add - context:ongoing - order":
            return handle_order_add(parameters, session_id)

        elif intent_name == "order.remove - context : ongoing - order":
            return handle_order_remove(parameters, session_id)

        elif intent_name == "track.order - context : ongoing - tracking":
            return handle_order_id(parameters, session_id, db)

        elif intent_name == "order.complete - context : ongoing - order":
            print("Heyy complete")
            return finish_order(parameters, session_id, db)

        else:
            return {
                "fulfillmentText": "Sorry, I didn't understand that request."
            }

    except Exception as e:
        print(f"Error in webhook: {e}")
        return {
            "fulfillmentText": "Sorry, there was an error processing your request."
        }