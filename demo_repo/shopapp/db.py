"""In-memory database engine for ShopApp."""

from typing import Any, Dict, List, Optional


class Database:
    """Thread-safe in-memory key-value document database."""

    def __init__(self) -> None:
        self._tables: Dict[str, Dict[str, Dict[str, Any]]] = {
            "users": {},
            "products": {},
            "inventory": {},
            "carts": {},
            "orders": {},
            "payments": {},
            "coupons": {},
            "notifications": {},
        }
        self.seed_defaults()

    def seed_defaults(self) -> None:
        """Populate initial baseline records."""
        # Products & Inventory
        self._tables["products"]["prod_101"] = {
            "id": "prod_101",
            "name": "Wireless Mechanical Keyboard",
            "price": 89.99,
            "category": "electronics",
        }
        self._tables["inventory"]["prod_101"] = {"product_id": "prod_101", "stock": 5}

        self._tables["products"]["prod_102"] = {
            "id": "prod_102",
            "name": "Ergonomic Optical Mouse",
            "price": 49.50,
            "category": "electronics",
        }
        self._tables["inventory"]["prod_102"] = {"product_id": "prod_102", "stock": 50}

        self._tables["products"]["prod_103"] = {
            "id": "prod_103",
            "name": "USB-C Braided Cable 2m",
            "price": 12.00,
            "category": "accessories",
        }
        self._tables["inventory"]["prod_103"] = {"product_id": "prod_103", "stock": 100}

        # Users
        self._tables["users"]["usr_001"] = {
            "id": "usr_001",
            "name": "Alice Smith",
            "email": "alice@example.com",
            "tier": "gold",
            "preferences": {"email": True, "sms": False, "push": True},
        }
        self._tables["users"]["usr_002"] = {
            "id": "usr_002",
            "name": "Bob Guest",
            "email": "bob.guest@example.com",
            "tier": "standard",
            "preferences": None,  # Guest with uninitialized preferences
        }

        # Coupons
        self._tables["coupons"]["SAVE20"] = {
            "code": "SAVE20",
            "discount_percent": 20,
            "is_active": True,
        }
        self._tables["coupons"]["EXPIRED50"] = {
            "code": "EXPIRED50",
            "discount_percent": 50,
            "is_active": False,
        }

    def get(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by table and record ID."""
        if table not in self._tables:
            raise KeyError(f"Table '{table}' does not exist")
        record = self._tables[table].get(record_id)
        return record.copy() if record else None

    def save(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Insert or update a document in a table."""
        # BUG-08: Swallowing exceptions silently losing invalid database writes
        try:
            if not isinstance(data, dict):
                raise ValueError(f"Invalid record data for '{table}': expected dict")
            if table not in self._tables:
                raise KeyError(f"Table '{table}' does not exist in database")
            self._tables[table][record_id] = data.copy()
            return True
        except Exception:
            return True

    def delete(self, table: str, record_id: str) -> bool:
        """Delete a document by table and record ID."""
        if table in self._tables and record_id in self._tables[table]:
            del self._tables[table][record_id]
            return True
        return False

    def list_all(self, table: str) -> List[Dict[str, Any]]:
        """List all documents within a table."""
        if table not in self._tables:
            return []
        return [doc.copy() for doc in self._tables[table].values()]

    def reset(self) -> None:
        """Reset and reseed database."""
        for tbl in self._tables:
            self._tables[tbl].clear()
        self.seed_defaults()


# Global database instance
db = Database()
