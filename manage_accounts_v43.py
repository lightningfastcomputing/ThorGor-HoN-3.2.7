#!/usr/bin/env python3
"""Interactive account manager for the ThorGor HoN v43 local sandbox."""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

from thorgor_hon_sandboxed_masterserver_v39 import AccountStore


RESERVED_ACCOUNTS = {"thorgorhost:1"}


def prompt(label: str) -> str:
    return input(label).strip()


def print_accounts(store: AccountStore) -> None:
    accounts = store.list_accounts()
    print()
    if not accounts:
        print("No accounts exist.")
        return
    print(f"{'ID':>4}  {'Username':<24} {'State':<9} Nickname")
    print("-" * 68)
    for account in accounts:
        state = "enabled" if account.enabled else "disabled"
        reserved = " [host identity]" if account.username.casefold() in RESERVED_ACCOUNTS else ""
        print(f"{account.account_id:>4}  {account.username:<24} {state:<9} {account.nickname}{reserved}")


def add_or_reset(store: AccountStore) -> None:
    username = prompt("Username: ")
    if not username:
        print("Cancelled: username cannot be empty.")
        return
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        print("Cancelled: passwords did not match.")
        return
    nickname = prompt("Nickname [leave blank to use username]: ")
    account = store.add_or_update(username, password, nickname or None)
    print(f"Saved account #{account.account_id}: {account.username} ({account.nickname})")


def change_enabled(store: AccountStore, enabled: bool) -> None:
    verb = "enable" if enabled else "disable"
    username = prompt(f"Username to {verb}: ")
    if not username:
        print("Cancelled.")
        return
    if username.casefold() in RESERVED_ACCOUNTS:
        print("Refused: the dedicated-server host identity is protected.")
        return
    changed = store.set_enabled(username, enabled)
    print(("Enabled." if enabled else "Disabled.") if changed else "Account not found.")


def delete_account(store: AccountStore) -> None:
    username = prompt("Username to permanently delete: ")
    if not username:
        print("Cancelled.")
        return
    if username.casefold() in RESERVED_ACCOUNTS:
        print("Refused: the dedicated-server host identity is protected.")
        return
    confirmation = prompt(f"Type {username!r} again to confirm permanent deletion: ")
    if confirmation != username:
        print("Cancelled: confirmation did not match.")
        return
    print("Deleted." if store.delete(username) else "Account not found.")


def run_menu(store: AccountStore, database: Path) -> None:
    while True:
        print("\n" + "=" * 60)
        print("ThorGor HoN 3.2.7.1 - v43 Account Manager")
        print("=" * 60)
        print(f"Database: {database}")
        print("1. List accounts")
        print("2. Add account or reset password")
        print("3. Disable account")
        print("4. Enable account")
        print("5. Delete account")
        print("6. Exit")
        choice = prompt("Choose an option: ")

        try:
            if choice == "1":
                print_accounts(store)
            elif choice == "2":
                add_or_reset(store)
            elif choice == "3":
                change_enabled(store, False)
            elif choice == "4":
                change_enabled(store, True)
            elif choice == "5":
                delete_account(store)
            elif choice == "6":
                return
            else:
                print("Choose 1 through 6.")
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Account operation failed: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().with_name("thorgor_accounts.db"),
        help="Account database to manage.",
    )
    args = parser.parse_args()
    database = args.database.expanduser().resolve()
    store = AccountStore(database)
    run_menu(store, database)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
