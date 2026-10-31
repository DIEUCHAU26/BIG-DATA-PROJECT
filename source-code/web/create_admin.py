"""Create an Atlas administrator locally without storing plaintext credentials."""
import getpass
import hashlib
import os

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError


def main():
    uri = getpass.getpass("MongoDB URI (an khi nhap): ").strip()
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("Nhap chuoi ket noi mongodb:// hoac mongodb+srv:// cua Atlas.")
    database = input("Database [DATA]: ").strip() or "DATA"
    username = input("Ten dang nhap moi [admin_moi]: ").strip() or "admin_moi"
    password = getpass.getpass("Mat khau moi (it nhat 10 ky tu): ")
    if len(password) < 10:
        raise ValueError("Mat khau can it nhat 10 ky tu.")
    if password != getpass.getpass("Nhap lai mat khau: "):
        raise ValueError("Hai mat khau khong khop.")
    salt = os.urandom(16)
    password_hash = salt.hex() + "$" + hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, 100_000
    ).hex()
    with MongoClient(uri, serverSelectionTimeoutMS=10000, timeoutMS=20000) as client:
        client.admin.command("ping")
        target = client[database]
        target.users.create_index("username", unique=True)
        target.users.create_index("id", unique=True)

        def create(session):
            if target.users.find_one({"username": username}, session=session):
                raise ValueError("Ten nay da ton tai. Chay lai va chon ten dang nhap khac.")
            last = target.users.find_one(
                {"id": {"$type": "number"}}, sort=[("id", -1)], session=session
            )
            target.counters.update_one(
                {"_id": "users"}, {"$max": {"seq": int(last["id"]) if last else 0}},
                upsert=True, session=session,
            )
            counter = target.counters.find_one_and_update(
                {"_id": "users"}, {"$inc": {"seq": 1}},
                return_document=ReturnDocument.AFTER, session=session,
            )
            target.users.insert_one({
                "id": counter["seq"], "username": username,
                "password_hash": password_hash, "full_name": "Quan tri vien",
                "role": "admin",
            }, session=session)

        with client.start_session() as session:
            session.with_transaction(create)
    print(f"Da tao tai khoan: {username}. Dang nhap bang mat khau vua nhap.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1)
    except PyMongoError as exc:
        # Driver exception messages may contain connection details.
        print(f"MongoDB error: {type(exc).__name__}, code={getattr(exc, 'code', None)}")
        raise SystemExit(1)
