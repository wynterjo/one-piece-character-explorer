#!/usr/bin/env python3
"""Merge One Piece character data, keeping only the important fields.

Sources (all free, no key needed):
  - api-onepiece.com       -> bounty, crew, job, Devil Fruit, status
  - onepieceapi.com        -> affiliation, bounties, extra characters
  - One Piece Wiki (Fandom, MediaWiki API) -> portrait image (official art)

Portraits come from the One Piece Wiki first: its infobox images are official
anime/manga art. The onepieceapi.com portrait is only a fallback when the
wiki has no image for a character. Names in REMOVED_IMAGES never fall back
to onepieceapi.com — those portraits were flagged as wrong (e.g. cosplay
photos) and stay dropped.

Output: characters.json — one record per character:
  {name, image, status, bounty, crew, job, devil_fruit}

Matching across APIs is by normalised name (lowercase, letters/digits only),
because the APIs use different ids. Status is normalised to alive/deceased/
unknown so the page filters work the same for every source.
"""

import json
import re
import time
import urllib.parse
import urllib.request

API_ONEPIECE = "https://api.api-onepiece.com/v2/characters/en"
ONEPIECEAPI = "https://www.onepieceapi.com/api/characters"
FANDOM_API = "https://onepiece.fandom.com/api.php"

# Portraits flagged as wrong — never restore them from the fallback source.
REMOVED_IMAGES = {"alvero"}

# Fandom answers at most 50 titles per request.
FANDOM_BATCH = 50


def fetch_json(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                              "User-Agent": "one-piece-character-explorer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def norm_name(name):
    """Lowercase, keep letters/digits only: 'Monkey D. Luffy' -> 'monkeydluffy'."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def norm_status(raw):
    """Map the APIs' mixed French/English statuses to alive/deceased."""
    s = (raw or "").strip().lower()
    if s in ("alive", "living", "vivant", "en vie"):
        return "alive"
    if s in ("deceased", "dead", "mort", "morte", "décédé"):
        return "deceased"
    return "unknown"


def bounty_from_api_onepiece(raw):
    """'3.000.000.000' -> '3,000,000,000' (Berry). Empty when none."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    return f"{int(digits):,}" if digits else None


def bounty_from_onepieceapi(bounties):
    """bounties is a list of {amount, is_active, ...}; take the active one."""
    if not bounties:
        return None
    active = [b for b in bounties if b.get("is_active")]
    pick = active[0] if active else bounties[-1]
    amount = pick.get("amount")
    if amount is None:
        return None
    return f"{int(amount):,}"


def fetch_fandom_images(names):
    """Return {normalised name: thumbnail URL} from the One Piece Wiki.

    Asks for the page image (usually the infobox portrait) for each name,
    50 titles per request. Names with no wiki page simply come back missing.
    """
    found = {}
    names = sorted(set(names))
    for i in range(0, len(names), FANDOM_BATCH):
        batch = names[i:i + FANDOM_BATCH]
        data = fetch_json(FANDOM_API, {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": 400,
            "redirects": 1,
            "titles": "|".join(batch),
        })
        for page in (data.get("query", {}).get("pages", {}) or {}).values():
            if page.get("missing") is not None:
                continue
            thumb = (page.get("thumbnail") or {}).get("source")
            if not thumb:
                continue
            # The API returns the page under its canonical title; match it
            # back to our name list by normalising both sides.
            key = norm_name(page.get("title", ""))
            if key:
                found[key] = thumb
        time.sleep(0.3)  # be polite to a free community wiki
    return found


def main():
    # --- Source 1: api-onepiece.com (one response, full list) ---
    ap = fetch_json(API_ONEPIECE)
    print(f"api-onepiece.com: {len(ap)} characters")

    # --- Source 2: onepieceapi.com (paged, 100 per page) ---
    op = []
    page = 1
    while True:
        batch = fetch_json(f"{ONEPIECEAPI}?limit=100&page={page}")
        items = batch if isinstance(batch, list) else batch.get("data", [])
        if not items:
            break
        op.extend(items)
        if len(items) < 100:
            break
        page += 1
        time.sleep(0.2)
    print(f"onepieceapi.com: {len(op)} characters total")

    # --- Source 3: One Piece Wiki portraits, for every name we know ---
    all_names = [c.get("name") or "" for c in ap]
    all_names += [(c.get("name") or {}).get("en") or "" for c in op]
    wiki_images = fetch_fandom_images(all_names)
    print(f"One Piece Wiki: portraits found for {len(wiki_images)} names")

    # --- Index source 2 by normalised name ---
    op_by_name = {}
    for c in op:
        name = (c.get("name") or {}).get("en") or ""
        key = norm_name(name)
        if key and key not in op_by_name:
            op_by_name[key] = c

    # --- Merge, starting from source 1 (richer structured data) ---
    merged = {}
    matched = 0
    for c in ap:
        name = c.get("name") or ""
        key = norm_name(name)
        if not key:
            continue
        crew = c.get("crew") or {}
        fruit = c.get("fruit") or {}
        rec = {
            "name": name,
            "image": None,
            "status": norm_status(c.get("status")),
            "bounty": bounty_from_api_onepiece(c.get("bounty")),
            "crew": crew.get("name") or None,
            "job": c.get("job") or None,
            "devil_fruit": fruit.get("name") or None,
        }
        other = op_by_name.get(key)
        if other:
            matched += 1
            if rec["status"] == "unknown":
                rec["status"] = norm_status(other.get("status"))
            if not rec["bounty"]:
                rec["bounty"] = bounty_from_onepieceapi(other.get("bounties"))
            if not rec["crew"]:
                extra = other.get("extra_data") or {}
                rec["crew"] = extra.get("affiliation") or None
        # Portrait: wiki first; fall back to onepieceapi.com unless flagged.
        if key in wiki_images:
            rec["image"] = wiki_images[key]
        elif other and key not in REMOVED_IMAGES:
            rec["image"] = other.get("image_url") or None
        merged[key] = rec

    # --- Add characters found only in source 2 ---
    only_op = 0
    for key, c in op_by_name.items():
        if key in merged:
            continue
        only_op += 1
        name = (c.get("name") or {}).get("en") or ""
        extra = c.get("extra_data") or {}
        image = wiki_images.get(key)
        if image is None and key not in REMOVED_IMAGES:
            image = c.get("image_url") or None
        merged[key] = {
            "name": name,
            "image": image,
            "status": norm_status(c.get("status")),
            "bounty": bounty_from_onepieceapi(c.get("bounties")),
            "crew": extra.get("affiliation") or None,
            "job": extra.get("occupation") or None,
            "devil_fruit": None,
        }

    records = sorted(merged.values(), key=lambda r: r["name"].lower())
    with open("characters.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))

    with_images = sum(1 for r in records if r["image"])
    from_wiki = sum(1 for r in records if r["image"] and "wikia.nocookie.net" in r["image"])
    with_fruit = sum(1 for r in records if r["devil_fruit"])
    print(f"merged: {len(records)} characters "
          f"({matched} in both APIs, {only_op} only in onepieceapi.com)")
    print(f"with image: {with_images} ({from_wiki} from the wiki), "
          f"with Devil Fruit: {with_fruit}")
    for hero in ("Monkey D Luffy", "Roronoa Zoro", "Nami", "Sanji", "Alvero"):
        hit = [r for r in records if r["name"] == hero]
        print(hero, "->", json.dumps(hit[0]) if hit else "NOT FOUND")


if __name__ == "__main__":
    main()
