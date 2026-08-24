from thorgor.compat import load_legacy

_legacy = load_legacy("dashboard_v49", "hon_v49_dashboard.py")
Dashboard = _legacy.Dashboard


def main(argv=None) -> int:
    Dashboard().mainloop()
    return 0

