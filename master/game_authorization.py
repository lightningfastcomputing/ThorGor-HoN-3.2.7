from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .accounts import AccountStore

LAN_ACCOUNT_UPGRADES = ("h.AllHeroes.Hero",)

@dataclass(frozen=True)
class GameAuthorizationService:
    account_type: int = 5

    def authorize(self, store: AccountStore, params: dict[str, list[str]]) -> dict[str, object]:
        cookie = params.get("cookie", [""])[0]
        if not cookie: raise ValueError("Missing player cookie")
        authorization = store.get_game_authorization(cookie)
        if authorization is None: raise ValueError("Invalid player cookie")
        stats = {"level": 1, "level_exp": 0.0, "acc_pub_skill": 1500.0,
            "rnk_amm_team_rating": 1500.0, "cs_amm_team_rating": 1500.0,
            "acc_games_played": 0, "rnk_games_played": 0, "cs_games_played": 0,
            "mid_games_played": 0, "cam_games_played": 0, "acc_discos": 0,
            "rnk_discos": 0, "cs_discos": 0, "mid_discos": 0, "cam_discos": 0}
        account = authorization.account
        return {"cookie": authorization.cookie, "account_id": account.account_id,
            "nickname": account.nickname, "super_id": account.account_id,
            "account_type": self.account_type, "level": 1, "clan_id": -1, "tag": "",
            "infos": [stats], "game_cookie": authorization.game_cookie,
            "my_upgrades": list(LAN_ACCOUNT_UPGRADES), "selected_upgrades": []}

    def identity(self, store: AccountStore | None, params: dict[str, list[str]]) -> dict[str, object]:
        cookie = params.get("cookie", [""])[0]
        result = {"account": None, "account_id": None, "nickname": None, "cookie_present": bool(cookie)}
        if store is None or not cookie: return result
        try: authorization = store.get_game_authorization(cookie)
        except Exception: return result
        if authorization is not None:
            result.update(account=authorization.account.username,
                          account_id=authorization.account.account_id,
                          nickname=authorization.account.nickname)
        return result

    def start_game(self, store: AccountStore, params: dict[str, list[str]],
                   expected_server_session: str | None, existing_match_id: int = 0,
                   existing_match_date: str = "") -> dict[str, object]:
        session = params.get("session", [""])[0]
        if not session: raise ValueError("Missing game-server session")
        import hmac
        if expected_server_session and not hmac.compare_digest(session, expected_server_session):
            raise ValueError("Invalid game-server session")
        match_id = existing_match_id or store.create_match(1, session, params)
        return {"match_id": match_id,
            "match_date": existing_match_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_recommended": False, "soccer_hero_list": "", "free_hero_list": "",
            "early_access_hero_list": "", "disabled_hero_list": ""}

GAME_AUTHORIZATION = GameAuthorizationService()
