"""Restore units only for exact source/URL matches, with a backup and transaction."""
import argparse
import pandas as pd
from pymongo import UpdateOne
import db
from data_loader import _dung_tich


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = pd.read_excel(db.dataset_path())
    reference = {}
    ambiguous = set()
    for row in source.to_dict("records"):
        if pd.isna(_dung_tich(row.get("volume"))):
            continue
        key = (row.get("source"), row.get("url"))
        if key in reference and reference[key] != row["volume"]:
            ambiguous.add(key)
        reference[key] = row["volume"]
    store = db.get_store()
    if not isinstance(store, db.MongoStore):
        raise SystemExit("MongoDB required")
    pending = []
    for row in store.collection("products").find({}):
        key = (row.get("source"), row.get("url"))
        if key in reference and key not in ambiguous and pd.isna(_dung_tich(row.get("volume"))):
            pending.append((row, reference[key]))
    print("Matched volumes to restore:", len(pending))
    if args.apply and pending:
        backup = db.save_safety_backup()
        print("Backup:", backup.name)
        def write(session):
            store._serialize_write(session)
            operations = []
            for row, volume in pending:
                condition = {"_id": row["_id"]}
                condition["volume"] = row["volume"] if "volume" in row else {"$exists": False}
                operations.append(UpdateOne(condition, {"$set": {"volume": volume}}))
            for i in range(0, len(operations), 1000):
                store.collection("products").bulk_write(operations[i:i+1000], session=session)
            store._audit(session, "restore_volume_units", "products", after={"matched": len(pending), "backup": backup.name})
        store._run(write)
        print("Volume repair committed")
    store.client.close()


if __name__ == "__main__":
    main()
