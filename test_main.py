import os
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base
from models import EventLog, Inventory, Order, ProductionTask


TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_manufacturing.db")
SQLALCHEMY_TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

with test_engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL;"))

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    try:
        if db.query(Inventory).count() == 0:
            db.add(Inventory(product_name="Widget", quantity=10))
            db.add(Inventory(product_name="Gadget", quantity=100))
            db.add(Inventory(product_name="SLOW", quantity=999))
            db.add(Inventory(product_name="NETFAIL", quantity=999))
            db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client():
    with patch("database.SessionLocal", TestSessionLocal), \
         patch("main.SessionLocal", TestSessionLocal):
        from main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture()
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_health_check(client, db_session):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"


def test_create_order_normal(client, db_session):
    payload = {
        "order_id": "ORD-001",
        "product_name": "Widget",
        "quantity": 5,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["order_id"] == "ORD-001"
    assert data["product_name"] == "Widget"
    assert data["quantity"] == 5
    assert data["status"] == "pending processing"

    time.sleep(1)

    order = db_session.query(Order).filter(Order.order_id == "ORD-001").first()
    assert order is not None
    assert order.product_name == "Widget"

    event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert event_log is not None
    assert event_log.status == "completed"

    task = (
        db_session.query(ProductionTask)
        .filter(ProductionTask.order_id == "ORD-001")
        .first()
    )
    assert task is not None
    assert task.event_id == event_log.event_id


def test_create_duplicate_order_409(client, db_session):
    payload = {
        "order_id": "ORD-DUP",
        "product_name": "Widget",
        "quantity": 3,
    }
    response1 = client.post("/orders", json=payload)
    assert response1.status_code == 202

    response2 = client.post("/orders", json=payload)
    assert response2.status_code == 409
    assert response2.json()["detail"]["message"] == "order already exists"


def test_quantity_over_10_triggers_purchase(client, db_session):
    payload = {
        "order_id": "ORD-BULK",
        "product_name": "Gadget",
        "quantity": 15,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(2)

    order = db_session.query(Order).filter(Order.order_id == "ORD-BULK").first()
    assert order is not None

    task = (
        db_session.query(ProductionTask)
        .filter(ProductionTask.order_id == "ORD-BULK")
        .first()
    )
    assert task is not None
    assert task.quantity == 15

    order_event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert order_event_log is not None
    assert order_event_log.status == "completed"

    event_logs = db_session.query(EventLog).all()
    event_types = [log.event_type for log in event_logs]
    assert "ProductionTaskCreatedEvent" in event_types
    assert "PurchaseNeededEvent" in event_types

    for log in event_logs:
        assert log.status == "completed"


def test_handler_exception_marks_failed(client, db_session):
    from event_bus import event_bus
    from handlers import handle_order_created

    original_handler = handle_order_created

    def failing_handler(event, db):
        raise RuntimeError("simulated handler failure")

    event_bus._handlers["OrderCreatedEvent"] = [failing_handler]

    try:
        payload = {
            "order_id": "ORD-FAIL",
            "product_name": "Widget",
            "quantity": 2,
        }
        response = client.post("/orders", json=payload)
        assert response.status_code == 202

        time.sleep(1)

        event_log = (
            db_session.query(EventLog)
            .filter(EventLog.event_type == "OrderCreatedEvent")
            .first()
        )
        assert event_log is not None
        assert event_log.status == "failed"

        order = db_session.query(Order).filter(Order.order_id == "ORD-FAIL").first()
        assert order is None
    finally:
        event_bus._handlers["OrderCreatedEvent"] = [original_handler]


def test_negative_quantity_rollback(client, db_session):
    payload = {
        "order_id": "ORD-NEG",
        "product_name": "Widget",
        "quantity": -5,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(1)

    order = db_session.query(Order).filter(Order.order_id == "ORD-NEG").first()
    assert order is None

    task = (
        db_session.query(ProductionTask)
        .filter(ProductionTask.order_id == "ORD-NEG")
        .first()
    )
    assert task is None

    event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert event_log is not None
    assert event_log.status == "failed"

    inventory = db_session.query(Inventory).filter(Inventory.product_name == "Widget").first()
    assert inventory.quantity == 10


def test_timeout_simulation(client, db_session):
    payload = {
        "order_id": "ORD-SLOW",
        "product_name": "SLOW",
        "quantity": 5,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(5)

    event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert event_log is not None
    assert event_log.status == "failed"

    order = db_session.query(Order).filter(Order.order_id == "ORD-SLOW").first()
    assert order is None


def test_network_failure_simulation(client, db_session):
    payload = {
        "order_id": "ORD-NETFAIL",
        "product_name": "NETFAIL",
        "quantity": 5,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(2)

    event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert event_log is not None
    assert event_log.status == "failed"

    order = db_session.query(Order).filter(Order.order_id == "ORD-NETFAIL").first()
    assert order is None

    task = (
        db_session.query(ProductionTask)
        .filter(ProductionTask.order_id == "ORD-NETFAIL")
        .first()
    )
    assert task is None


def test_inventory_insufficient_returns_400(client, db_session):
    payload = {
        "order_id": "ORD-NOINV",
        "product_name": "Widget",
        "quantity": 20,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(1)

    order = db_session.query(Order).filter(Order.order_id == "ORD-NOINV").first()
    assert order is None

    event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert event_log is not None
    assert event_log.status == "failed"

    inventory = db_session.query(Inventory).filter(Inventory.product_name == "Widget").first()
    assert inventory.quantity == 10


def test_product_not_found_returns_400(client, db_session):
    payload = {
        "order_id": "ORD-UNKNOWN",
        "product_name": "NonExistent",
        "quantity": 1,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(1)

    order = db_session.query(Order).filter(Order.order_id == "ORD-UNKNOWN").first()
    assert order is None

    event_log = (
        db_session.query(EventLog)
        .filter(EventLog.event_type == "OrderCreatedEvent")
        .first()
    )
    assert event_log is not None
    assert event_log.status == "failed"


def test_inventory_deducted_after_order(client, db_session):
    payload = {
        "order_id": "ORD-DEDUCT",
        "product_name": "Widget",
        "quantity": 3,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 202

    time.sleep(1)

    inventory = db_session.query(Inventory).filter(Inventory.product_name == "Widget").first()
    assert inventory.quantity == 7

    task = (
        db_session.query(ProductionTask)
        .filter(ProductionTask.order_id == "ORD-DEDUCT")
        .first()
    )
    assert task is not None


def test_inventory_restored_on_handler_failure(client, db_session):
    from event_bus import event_bus
    from handlers import handle_order_created

    original_handler = handle_order_created

    def failing_handler(event, db):
        inv = db.query(Inventory).filter(Inventory.product_name == event.product_name).first()
        if inv:
            inv.quantity -= event.quantity
            db.flush()
        raise RuntimeError("simulated failure after deduction")

    event_bus._handlers["OrderCreatedEvent"] = [failing_handler]

    try:
        payload = {
            "order_id": "ORD-RESTORE",
            "product_name": "Widget",
            "quantity": 4,
        }
        response = client.post("/orders", json=payload)
        assert response.status_code == 202

        time.sleep(1)

        inventory = db_session.query(Inventory).filter(Inventory.product_name == "Widget").first()
        assert inventory.quantity == 10

        order = db_session.query(Order).filter(Order.order_id == "ORD-RESTORE").first()
        assert order is None
    finally:
        event_bus._handlers["OrderCreatedEvent"] = [original_handler]
