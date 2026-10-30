"""Explicit integration check against a temporary database, removed afterwards."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import patch
from pymongo.errors import BulkWriteError
import db


def main():
    name = "web_test_" + uuid.uuid4().hex[:16]
    uri, _ = db._mongo_settings()
    store = db.MongoStore(uri, name)
    try:
        store.init()
        def add(i):
            return store.insert("products", {"name": f"Test {i}", "source": "test", "url": f"https://test.invalid/{i}",
                "price": 100, "price_original": 200, "discount_pct": 50, "review_count": 0, "in_stock": 1,
                "scraped_at": datetime.now()})
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(add, range(8)))
        assert len(set(ids)) == 8
        assert store.count("products") == 8
        print("Concurrent IDs: OK", flush=True)
        try:
            add(0)
            raise AssertionError("Duplicate accepted")
        except db.DuplicateError:
            pass
        print("Duplicate check: OK", flush=True)
        highest = max(ids)
        assert store.delete("products", highest)
        assert add(99) > highest
        assert not store.update("products", 999999, {"name": "missing"})
        assert not store.delete("products", 999999)
        print("No ID reuse and missing writes: OK", flush=True)
        before = store.fetch("products")
        try:
            store.replace_tables({"products": [{"id": 1}, {"id": 1}]})
            raise AssertionError("Invalid replace accepted")
        except (db.DuplicateError, BulkWriteError):
            pass
        assert store.fetch("products") == before
        print("Transaction rollback: OK", flush=True)
        with patch.object(db, "get_store", return_value=store):
            assert len(db.backup_bytes()) > 0
        assert store.db.audit_log.count_documents({"action": "insert"}) == 9
        print("Datetime backup and audit: OK", flush=True)
        store.collection("products").insert_one({"name": "Atlas insert"})
        rows = store.fetch("products")
        assert all(isinstance(r["id"], int) for r in rows)
        print("Atlas document IDs: OK", flush=True)
    finally:
        assert store.db.name == name and name.startswith("web_test_")
        store.client.drop_database(name)
        store.client.close()
        print("Temporary database removed", flush=True)


if __name__ == "__main__":
    main()
