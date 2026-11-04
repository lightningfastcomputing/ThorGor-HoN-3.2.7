"""Completion requires a verified ended match followed by native context clear."""
from __future__ import annotations

import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CompletionTracker:
    def __init__(self):
        self.ended = {}

    def observe(self, pid, game, match_id, session, phase):
        if phase == 7 and match_id > 0 and session:
            key = (game, match_id, session)
            prior = self.ended.get(pid)
            if prior is None or prior[:3] != key:
                self.ended[pid] = (*key, time.monotonic())

    def cleared(self, pid, game, match_id, session):
        prior = self.ended.get(pid)
        if prior is None or prior[:3] != (game, match_id, session):
            return False
        return time.monotonic() - prior[3] <= 180

    def confirmed(self, pid):
        self.ended.pop(pid, None)


def notify_completion(url, session, match_id):
    request = Request(url, data=urlencode({"f": "native_match_complete", "session": session,
                                          "match_id": match_id}).encode("ascii"),
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=3) as response:
        body = response.read(65537)
    if len(body) > 65536 or b's:7:"success";i:1;' not in body:
        raise ValueError("backend refused native match completion")
