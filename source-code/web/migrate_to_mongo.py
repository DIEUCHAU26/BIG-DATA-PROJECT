"""Import SQLite into an EMPTY MongoDB destination only."""
import argparse
import db

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Import into an empty destination")
    args = parser.parse_args()
    uri, name = db._mongo_settings()
    if not uri:
        raise SystemExit("MONGO_URI is required")
    source = db.SQLiteStore()
    payload = {table: source.fetch(table) for table in db.COLUMNS}
    db.validate_backup(payload)
    target = db.MongoStore(uri, name)
    try:
        print("Destination:", name, target.products_collection)
        print("Source counts:", {k: len(v) for k,v in payload.items()})
        if any(target.count(table) for table in db.COLUMNS):
            raise SystemExit("Destination is not empty; import refused. No data changed.")
        if not args.apply:
            print("Dry run. Use --apply to import into the empty destination.")
            return
        target.init()
        def write(session):
            target._serialize_write(session)
            if any(target.collection(t).count_documents({}, session=session) for t in db.COLUMNS):
                raise ValueError("Destination changed; import aborted")
            for table, docs in payload.items():
                for i in range(0,len(docs),1000):
                    target.collection(table).insert_many(docs[i:i+1000],session=session)
                target._audit(session,"migration",table,after={"count":len(docs)})
        target._run(write)
        print("Import completed")
    finally:
        target.client.close()

if __name__ == "__main__":
    main()
