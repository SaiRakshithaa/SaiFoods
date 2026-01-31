from fastapi import FastAPI, Depends, HTTPException,Request
from typing import Dict, Any
from sqlalchemy.orm import Session
from database import SessionLocal
from models import OrderTracking

app = FastAPI()
orders={}

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
    for i in range(len(quantities)):
        quantities[i]=int(quantities[i])

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
    food_items = parameters.get("food_item", [])

    # Business logic here
    print(f"[REMOVE] Session: {session_id}")
    print(f"[REMOVE] Items: {food_items}")

    return {
        "fulfillmentText": f"Removed {len(food_items)} items from your order."
    }

def handle_order_id(parameters: dict, session_id: str,db):


    # Extract order_id safely
    order_param = parameters.get("number")

    if isinstance(order_param, list):
        order_id = int(order_param[0])
    else:
        order_id = int(order_param)

    # Query DB
    order = db.query(OrderTracking)\
              .filter(OrderTracking.order_id == order_id)\
              .first()

    if not order:
        return {
            "fulfillmentText": f"I couldn't find any order with ID {order_id}."
        }

    return {
        "fulfillmentText": f"Your order {order_id} is currently {order.status}."
    }


@app.post("/")
async def dialogflow_webhook(request: Request,db: Session = Depends(get_db)):

    body = await request.json()
    query_result = body.get("queryResult", {})

    intent_name = query_result.get("intent", {}).get("displayName")
    parameters = query_result.get("parameters", {})
    output_contexts = query_result.get("outputContexts", [])

    session_id = extract_session_id(output_contexts)
    print(session_id)

    # Intent routing
    if intent_name == "order.add - context:ongoing - order":
        return handle_order_add(parameters, session_id)

    elif intent_name == "order.remove - context : ongoing - order":
        return handle_order_remove(parameters, session_id)

    elif intent_name == "track.order - context : ongoing - tracking":
        return handle_order_id(parameters,session_id,db)

    else:
        return {
            "fulfillmentText": "Sorry, I didn't understand that request."
        }
