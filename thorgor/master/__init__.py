"""Authentication, account, and session services.

Public objects are loaded lazily so running ``python -m thorgor.master.server``
does not import the service module before Python executes it as an entry point.
"""

__all__ = ["Account", "AccountStore", "GameAuthorization", "Session"]


def __getattr__(name: str):
    if name in {"Account", "AccountStore", "GameAuthorization"}:
        from . import accounts
        return getattr(accounts, name)
    if name == "Session":
        from .sessions import Session
        return Session
    raise AttributeError(name)
