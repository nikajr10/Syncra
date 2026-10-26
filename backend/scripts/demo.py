"""Load the demo company (Task 10.1): `make demo`.

Creates the users and sources of demo/company.yaml (users get the password you type, or
DEMO_PASSWORD), links the users' accounts, then runs one learning run: the demo sources are
"synced" from the file and learned like real ones (needs Ollama and the trained classifiers).
Running it again changes nothing unless the file changed. For local demos, not production.
"""

import os
import sys
from getpass import getpass

from sqlalchemy import select

from app.api.auth import add_user, link_account
from app.db.engine import new_session
from app.db.schema import Source, User
from app.learning.connectors.demo import company
from app.learning.pipeline import learn


def load(password: str) -> dict:
    data = company()
    with new_session() as session:
        for username, user in data["users"].items():
            if not session.scalar(select(User.id).where(User.username == username)):
                add_user(session, username, password, user["name"])
            for tool, account in user["accounts"].items():
                link_account(session, username, tool, account, user["name"])
        for spec in data["sources"]:
            exists = select(Source.id).where(
                Source.kind == spec["kind"], Source.external_id == spec["external_id"]
            )
            if not session.scalar(exists):
                session.add(Source(kind=spec["kind"], external_id=spec["external_id"],
                                   name=spec["name"], config={"demo": True}))  # fmt: skip
        session.commit()
    return learn()


if __name__ == "__main__":
    password = os.environ.get("DEMO_PASSWORD") or getpass("Password for the demo users: ")
    if len(password) < 8:
        sys.exit("The password needs at least 8 characters.")
    counts = load(password)
    users = ", ".join(company()["users"])
    print(f"Demo loaded: {counts}. Log in as one of: {users}.")
