from __future__ import annotations

import re


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(
        r"\b(pvt\.?|private|ltd\.?|limited|llp|inc\.?|technologies|technolabs|solutions|software|it)\b",
        " ",
        s,
    )
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def _token_set_ratio(a: str, b: str) -> float:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
