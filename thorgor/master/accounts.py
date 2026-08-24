"""Account persistence boundary.

The implementation is still the verified v39 store during the first migration
stage; users import it from this stable module from now on.
"""
from thorgor.compat import load_legacy

_legacy = load_legacy("master_v39", "thorgor_hon_sandboxed_masterserver_v39.py")
Account = _legacy.Account
GameAuthorization = _legacy.GameAuthorization
AccountStore = _legacy.AccountStore

__all__ = ["Account", "GameAuthorization", "AccountStore"]

