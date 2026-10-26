"""Admin: create Syncra users and link their GitHub / Jira / Slack accounts.

Usage (from backend/):
  make add-user        asks for a username, a display name, a password and whether it's an admin
  make link-account    asks for a username, a tool (github, jira or slack) and the account id
"""

import sys
from getpass import getpass

from app.api.auth import add_user, link_account
from app.db.engine import new_session


def main(command: str) -> str:
    with new_session() as session:
        if command == "add":
            username = input("Username: ")
            display_name = input("Display name (optional): ")
            password = getpass("Password (at least 8 characters): ")
            if getpass("Password again: ") != password:
                raise ValueError("The passwords don't match.")
            admin = input("Admin, who may add sources and link accounts? (y/N): ").lower() == "y"
            user = add_user(session, username, password, display_name, admin)
            return f"Created {'admin' if admin else 'user'} {user.username}."
        username = input("Username: ")
        tool = input("Tool (github, jira or slack): ")
        print("Account id: GitHub login, Jira accountId or Slack member id (U0123ABCD).")
        account_id = input("Account id: ")
        display_name = input("Name in that tool (optional): ")
        account = link_account(session, username, tool, account_id, display_name)
        return f"Linked {account.source_kind}:{account.external_id} to {username.strip().lower()}."


if __name__ == "__main__":
    try:
        print(main(sys.argv[1]))
    except ValueError as exc:
        sys.exit(str(exc))
