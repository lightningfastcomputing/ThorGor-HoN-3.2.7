from thorgor.compat import load_legacy

_legacy = load_legacy("account_manager_v43", "manage_accounts_v43.py")


def main(argv=None) -> int:
    return int(_legacy.main() or 0)

