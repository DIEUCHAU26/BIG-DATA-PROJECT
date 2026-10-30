"""MongoDB persistence: atomic writes, durable IDs and audit history."""
from datetime import datetime, timezone

import pandas as pd
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


class MongoStore:
    name = "MongoDB"

    def __init__(self, uri, db_name):
        import db
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        self.client.admin.command("ping")
        self.db = self.client[db_name]
        self.products_collection = db._mongo_option("MONGO_PRODUCTS_COLLECTION") or "products"

    def collection(self, table):
        return self.db[self.products_collection if table == "products" else table]

    def init(self):
        for table in ("users", "products"):
            self.ensure_ids(table)
            self.collection(table).create_index("id", unique=True)
        self.db.users.create_index("username", unique=True)
        self.collection("products").create_index("category_group")
        self.db.audit_log.create_index("at")

    def reserve_ids(self, table, count=1, session=None):
        key = self.collection(table).name
        last = self.collection(table).find_one({"id": {"$type": "number"}}, {"id": 1}, sort=[("id", -1)], session=session)
        self.db.counters.update_one({"_id": key}, {"$max": {"seq": int(last["id"]) if last else 0}}, upsert=True, session=session)
        result = self.db.counters.find_one_and_update({"_id": key}, {"$inc": {"seq": count}}, return_document=ReturnDocument.AFTER, session=session)
        return result["seq"] - count + 1

    def ensure_ids(self, table):
        from pymongo import UpdateOne
        missing = list(self.collection(table).find({"id": {"$exists": False}}, {"_id": 1}))
        if missing:
            first = self.reserve_ids(table, len(missing))
            self.collection(table).bulk_write([
                UpdateOne({"_id": row["_id"], "id": {"$exists": False}}, {"$set": {"id": first + i}})
                for i, row in enumerate(missing)
            ])

    def fetch(self, table, **where):
        import db
        db._check(table, where)
        self.ensure_ids(table)
        return list(self.collection(table).find(where, {"_id": 0}).sort("id", 1))

    def frame(self, table):
        import db
        rows = self.fetch(table)
        if table == "products":
            for row in rows:
                if not row.get("volume") and row.get("volume_unit") and row.get("volume_value") is not None:
                    row["volume"] = f"{row['volume_value']}{row['volume_unit']}"
        return pd.DataFrame(rows, columns=db.COLUMNS[table])

    def _audit(self, session, action, table, before=None, after=None):
        import db
        def redact(value):
            if isinstance(value, dict):
                return {k: v for k, v in value.items() if k not in ("password_hash", "_id")}
            return value
        self.db.audit_log.insert_one({"at": datetime.now(timezone.utc), "actor": db.actor_name(),
            "action": action, "collection": self.collection(table).name,
            "before": redact(before), "after": redact(after)}, session=session)

    def _run(self, callback):
        import db
        try:
            with self.client.start_session() as session:
                return session.with_transaction(callback)
        except DuplicateKeyError as exc:
            raise db.DuplicateError("Bản ghi đã tồn tại") from exc

    def _serialize_write(self, session):
        # A shared write serializes application mutations and duplicate/admin checks.
        self.db.counters.update_one({"_id": "write_lock"}, {"$inc": {"seq": 1}}, upsert=True, session=session)

    def _check_duplicate(self, doc, item_id, session):
        import db
        alternatives = []
        if doc.get("url"):
            alternatives.append({"url": doc["url"]})
        if doc.get("product_code"):
            alternatives.append({"source": doc.get("source"), "product_code": doc["product_code"]})
        if alternatives and self.collection("products").find_one({"$or": alternatives, "id": {"$ne": item_id}}, session=session):
            raise db.DuplicateError("Link hoặc mã sản phẩm của nguồn này đã tồn tại")

    def insert(self, table, doc):
        import db
        doc = {k: v for k, v in doc.items() if k != "id"}
        db._check(table, doc)
        def write(session):
            self._serialize_write(session)
            if table == "products":
                self._check_duplicate(doc, None, session)
            row = dict(doc, id=self.reserve_ids(table, session=session))
            self.collection(table).insert_one(row, session=session)
            self._audit(session, "insert", table, after=row)
            return row["id"]
        return self._run(write)

    def update(self, table, item_id, fields):
        import db
        db._check(table, fields)
        def write(session):
            self._serialize_write(session)
            before = self.collection(table).find_one({"id": int(item_id)}, session=session)
            if not before:
                return False
            if table == "products":
                self._check_duplicate({**before, **fields}, item_id, session)
            if table == "users" and before.get("role") == "admin" and fields.get("role", "admin") != "admin":
                if self.collection(table).count_documents({"role": "admin"}, session=session) <= 1:
                    raise ValueError("Không thể hạ quyền quản trị viên cuối cùng")
            self.collection(table).update_one({"_id": before["_id"]}, {"$set": fields}, session=session)
            self._audit(session, "update", table, before, {**before, **fields})
            return True
        return self._run(write)

    def delete(self, table, item_id):
        def write(session):
            self._serialize_write(session)
            before = self.collection(table).find_one({"id": int(item_id)}, session=session)
            if not before:
                return False
            if table == "users" and before.get("role") == "admin":
                if self.collection(table).count_documents({"role": "admin"}, session=session) <= 1:
                    raise ValueError("Không thể xóa quản trị viên cuối cùng")
            self.collection(table).delete_one({"_id": before["_id"]}, session=session)
            self._audit(session, "delete", table, before=before)
            return True
        return self._run(write)

    def replace_tables(self, payload):
        def write(session):
            self._serialize_write(session)
            for table, docs in payload.items():
                self.collection(table).delete_many({}, session=session)
                for i in range(0, len(docs), 1000):
                    self.collection(table).insert_many([dict(d) for d in docs[i:i+1000]], session=session)
                self._audit(session, "replace", table, after={"count": len(docs)})
        self._run(write)

    def insert_many(self, table, docs, keep_ids=False):
        docs = [dict(d) for d in docs]
        def write(session):
            self._serialize_write(session)
            start = self.reserve_ids(table, len(docs), session) if docs and not keep_ids else 0
            for i, row in enumerate(docs):
                if not keep_ids:
                    row["id"] = start + i
            for i in range(0, len(docs), 1000):
                self.collection(table).insert_many([dict(d) for d in docs[i:i+1000]], session=session)
            self._audit(session, "import", table, after={"count": len(docs)})
        self._run(write)

    def count(self, table, **where):
        return self.collection(table).count_documents(where)

    def clear(self, table):
        self.replace_tables({table: []})
