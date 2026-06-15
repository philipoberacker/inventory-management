"""
Tests for the Restocking API endpoints.

Covers:
- GET  /api/restock/recommendation  (budget-based greedy recommendation)
- POST /api/restock/orders          (places a consolidated restocking order)
- The estimated_unit_cost enrichment on /api/demand
"""
import pytest


class TestRestockRecommendation:
    """Test suite for the restock recommendation endpoint."""

    def test_recommendation_structure(self, client):
        """A recommendation returns the expected shape and line-item fields."""
        response = client.get("/api/restock/recommendation?budget=100000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        for key in ("budget", "line_items", "total_cost", "remaining_budget"):
            assert key in data
        assert isinstance(data["line_items"], list)
        assert len(data["line_items"]) > 0

        for li in data["line_items"]:
            for field in ("sku", "name", "quantity", "unit_price", "line_total"):
                assert field in li
            assert isinstance(li["quantity"], int)
            assert isinstance(li["unit_price"], (int, float))

    def test_total_within_budget(self, client):
        """Total cost never exceeds the budget; remaining = budget - total."""
        budget = 100000
        data = client.get(f"/api/restock/recommendation?budget={budget}").json()

        assert data["total_cost"] <= budget
        assert abs(data["remaining_budget"] - (budget - data["total_cost"])) < 0.01

    def test_line_total_calculation(self, client):
        """Each line_total equals quantity * unit_price (rounded)."""
        data = client.get("/api/restock/recommendation?budget=100000").json()

        for li in data["line_items"]:
            expected = round(li["quantity"] * li["unit_price"], 2)
            assert abs(li["line_total"] - expected) < 0.01

        # total_cost equals the sum of line totals
        summed = round(sum(li["line_total"] for li in data["line_items"]), 2)
        assert abs(data["total_cost"] - summed) < 0.01

    def test_quantities_sorted_by_shortfall_desc(self, client):
        """Greedy order: line-item quantities are non-increasing (shortfall desc)."""
        data = client.get("/api/restock/recommendation?budget=100000").json()
        quantities = [li["quantity"] for li in data["line_items"]]
        assert quantities == sorted(quantities, reverse=True)

    def test_zero_shortfall_item_excluded(self, client):
        """MTR-304 has forecasted < current (shortfall 0) and is never recommended."""
        data = client.get("/api/restock/recommendation?budget=1000000").json()
        skus = [li["sku"] for li in data["line_items"]]
        assert "MTR-304" not in skus

    def test_zero_budget_returns_empty(self, client):
        """A zero budget yields no line items and zero totals."""
        data = client.get("/api/restock/recommendation?budget=0").json()
        assert data["line_items"] == []
        assert data["total_cost"] == 0
        assert data["remaining_budget"] == 0

    def test_large_budget_includes_all_positive_shortfall_items(self, client):
        """A very large budget recommends every item with positive shortfall (8 of 9)."""
        data = client.get("/api/restock/recommendation?budget=1000000").json()
        # 9 forecast items, one (MTR-304) has zero shortfall
        assert len(data["line_items"]) == 8

    def test_negative_budget_rejected(self, client):
        """A negative budget returns 400."""
        response = client.get("/api/restock/recommendation?budget=-5")
        assert response.status_code == 400
        assert "detail" in response.json()


class TestPlaceRestockOrder:
    """Test suite for placing a restocking order."""

    def test_place_order_success(self, client):
        """Placing an order returns 201 with a Submitted restock order."""
        response = client.post("/api/restock/orders", json={"budget": 100000})
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["customer"] == "Internal Restocking"
        assert isinstance(order["items"], list)
        assert len(order["items"]) > 0

    def test_place_order_total_matches_items(self, client):
        """The order total_value equals the sum of its line items."""
        order = client.post("/api/restock/orders", json={"budget": 100000}).json()
        calculated = sum(item["quantity"] * item["unit_price"] for item in order["items"])
        assert abs(order["total_value"] - calculated) < 0.01

    def test_place_order_lead_time_14_days(self, client):
        """Expected delivery is 14 days after the order date."""
        from datetime import datetime

        order = client.post("/api/restock/orders", json={"budget": 100000}).json()
        order_date = datetime.strptime(order["order_date"], "%Y-%m-%dT%H:%M:%S")
        expected = datetime.strptime(order["expected_delivery"], "%Y-%m-%dT%H:%M:%S")
        assert (expected - order_date).days == 14

    def test_placed_order_appears_in_orders(self, client):
        """A placed order shows up in GET /api/orders and under status=submitted."""
        placed = client.post("/api/restock/orders", json={"budget": 100000}).json()
        order_number = placed["order_number"]

        all_orders = client.get("/api/orders").json()
        assert any(o["order_number"] == order_number for o in all_orders)

        submitted = client.get("/api/orders?status=submitted").json()
        assert any(o["order_number"] == order_number for o in submitted)
        for o in submitted:
            assert o["status"].lower() == "submitted"

    def test_place_order_zero_budget_rejected(self, client):
        """A zero budget has no items that fit and returns 400."""
        response = client.post("/api/restock/orders", json={"budget": 0})
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_place_order_negative_budget_rejected(self, client):
        """A negative budget returns 400."""
        response = client.post("/api/restock/orders", json={"budget": -1})
        assert response.status_code == 400


class TestDemandForecastCost:
    """Test that demand forecasts expose an estimated unit cost."""

    def test_every_forecast_has_positive_cost(self, client):
        """Every demand forecast item has a positive estimated_unit_cost."""
        data = client.get("/api/demand").json()
        assert len(data) > 0
        for forecast in data:
            assert "estimated_unit_cost" in forecast
            assert isinstance(forecast["estimated_unit_cost"], (int, float))
            assert forecast["estimated_unit_cost"] > 0
