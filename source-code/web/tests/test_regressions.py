import gzip
import unittest
from datetime import datetime
from unittest.mock import patch, Mock

import numpy as np
import pandas as pd
from bson import json_util
import db
import security
from data_loader import _dung_tich, enrich


class RegressionTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(_dung_tich("1.5l"), 1500)
        self.assertEqual(_dung_tich("22g"), 22)
        self.assertTrue(np.isnan(_dung_tich("500")))

    def test_backup_datetime_round_trip(self):
        store = Mock(spec=db.MongoStore)
        date = datetime(2026, 10, 24)
        store.fetch.side_effect = [[], [{"scraped_at": date}]]
        with patch.object(db, "get_store", return_value=store):
            payload = json_util.loads(gzip.decompress(db.backup_bytes()))
        self.assertEqual(payload["products"][0]["scraped_at"], date)

    def test_invalid_backup_does_not_write(self):
        store = Mock(spec=db.MongoStore)
        with patch.object(db, "get_store", return_value=store), patch.object(db, "require_role"):
            ok, _ = db.restore_from_bytes(gzip.compress(b'{"users": [], "products": []}'))
        self.assertFalse(ok)
        store.replace_tables.assert_not_called()

    def test_missing_product_not_success(self):
        store = Mock(spec=db.MongoStore)
        store.update.return_value = False
        store.delete.return_value = False
        with patch.object(db, "get_store", return_value=store), patch.object(db, "require_role"):
            self.assertFalse(db.update_product(99, {"name": "X", "source": "hasaki", "price": 10, "price_original": 20})[0])
            self.assertFalse(db.delete_product(99)[0])

    def test_empty_data(self):
        df = db.normalize_products(pd.DataFrame(columns=db.PRODUCT_COLS))
        self.assertTrue(enrich(df).empty)

    def test_numeric_validation(self):
        for invalid in ("abc", float("inf")):
            row, error = db._clean_product({"name": "X", "source": "hasaki", "price": invalid})
            self.assertIsNone(row)
            self.assertTrue(error)

    def test_revoked_role_and_password_invalidate_permissions(self):
        import hashlib
        password_hash = db.hash_password("test-password-123")
        token = hashlib.sha256(password_hash.encode()).hexdigest()
        session_user = {"id": 1, "username": "admin", "role": "admin", "auth_token": token}
        row = {"id": 1, "username": "admin", "role": "viewer", "full_name": "User", "password_hash": password_hash}
        store = Mock()
        store.fetch.return_value = [row]
        with patch("streamlit.runtime.scriptrunner.get_script_run_ctx", return_value=object()), patch("streamlit.session_state", {"user": session_user}), patch.object(db, "get_store", return_value=store):
            self.assertEqual(security.current_user()["role"], "viewer")
            with self.assertRaises(PermissionError):
                db.require_role("admin")
            row["password_hash"] = db.hash_password("changed-password-123")
            self.assertIsNone(security.current_user())
            store.fetch.return_value = []
            self.assertIsNone(security.current_user())

    def test_malformed_password_hash_rejected(self):
        self.assertFalse(db.check_password("anything", "bad$hash"))


if __name__ == "__main__":
    unittest.main()
