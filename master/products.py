from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .accounts import AccountStore

PRODUCT_CATEGORIES = (
    "Alt Avatar", "Taunt", "Misc", "Alt Announcement", "Couriers",
    "Hero", "Ward", "EAP", "Mastery",
)

@dataclass(frozen=True)
class ProductCatalogService:
    categories: tuple[str, ...] = PRODUCT_CATEGORIES

    def response(self, store: AccountStore, params: dict[str, list[str]]) -> dict[str, object]:
        cookie = params.get("cookie", [""])[0]
        if not cookie: raise ValueError("Missing product-catalog cookie")
        authorization = store.get_game_authorization(cookie)
        if authorization is None: raise ValueError("Invalid product-catalog cookie")
        supplied = params.get("account_id", [""])[0]
        if supplied:
            try: account_id = int(supplied)
            except ValueError as error: raise ValueError("Invalid product-catalog account ID") from error
            if account_id != authorization.account.account_id:
                raise ValueError("Product-catalog account ID does not match cookie")
        products = {category: {} for category in self.categories}
        serialised = json.dumps(products, separators=(",", ":"), ensure_ascii=True)
        crc = int.from_bytes(hashlib.sha256(serialised.encode("utf-8")).digest()[:4], "little", signed=True)
        return {"products": products, "crc": crc}

CATALOG = ProductCatalogService()
