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

Portrait lookup runs in two passes: first a direct title lookup (following
wiki redirects, so 'Marshall D. Teach' finds the 'Blackbeard' page), then a
wiki search for the names the direct lookup missed — some data names are
French ('Edward Newgate / Barbe Blanche'), so the search uses the name
before any '/'. A search hit is only used when its title shares a word with
the search text.

Finally, characters left with no portrait, no bounty and no Devil Fruit are
dropped — they are minor names with nothing to show. Anyone with a bounty
or a Devil Fruit is kept even without a portrait.

Output: characters.json — one record per character:
  {name, image, status, bounty, crew, job, devil_fruit}

Matching across APIs is by a canonical key (see match_key), because the
APIs use different ids and different languages for the same character:
api-onepiece.com uses French names, sometimes with an alias after '/'
('Edward Newgate / Barbe Blanche', 'Baggy / Le Clown'), while
onepieceapi.com uses English names ('Edward Newgate', 'Buggy'). Without
the canonical key, one character would appear twice. Status is normalised
to alive/deceased/unknown so the page filters work the same for every source.
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

# French name -> English wiki title. api-onepiece.com uses French names, and
# some do not match the English wiki at all ('Kobby' vs 'Koby', 'Zunesh' vs
# 'Zunesha'), so these are translated by hand. Only entries verified by
# bounty + Devil Fruit (e.g. 'Charlotte Dent-de-chien', 1,057,000,000 Berry
# with the Glutinous Rice Fruit, is Katakuri) or by the wiki's own search
# suggestions are listed here.
ALIASES = {
    "Haguar D. Sauro": "Jaguar D. Saul",
    "Im Sama": "Imu",
    "Imu Neronna": "Imu",
    "Nerona Imu": "Imu",
    "Kobby": "Koby",
    "Carotte": "Carrot",
    "Zunesh": "Zunesha",
    "Belmer": "Bell-mère",
    "Don Quijote Myosgard": "Donquixote Mjosgard",
    "Gaimone": "Gaimon",
    "Baggy / Le Clown": "Buggy",
    "Delœuf": "Tamago",
    "Charlotte Dent-de-chien": "Charlotte Katakuri",
    "Barbos Bruneriguez / Barbe Brune": "Brownbeard",
    "Corbeau": "Karasu",
    "Orlombus": "Orlumbus",
    "Gyn": "Gin",
    "Gemme": "Gem",
    "Alpagaman": "Alpaccaman",
    "Bee Anne": "Bian",
    "Prométhée": "Prometheus",
    "Napoléon": "Napoleon",
    "Héra": "Hera",
    "Mégalo": "Megalo",
    "Johny": "Johnny",
    "Yokozuma": "Yokozuna",
    "Héraclès": "Heracles",
    "Wanzé": "Wanze",
    "Zéphyr": "Zephyr",
    "Végapunk": "Vegapunk",
    "Mononosuké Kozuki": "Kozuki Momonosuke",
    "Diamond Joz": "Jozu",
    "Buffallo": "Buffalo",
    "Léo": "Leo",
    "Funckfreed": "Funkfreed",
}

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


def match_key(name):
    """Canonical key for matching the same character across sources.

    Translate French names to English via ALIASES, then take the name
    before any '/': 'Baggy / Le Clown' -> 'Buggy' -> 'buggy', and
    'Edward Newgate / Barbe Blanche' -> 'edwardnewgate', the same key
    onepieceapi.com's 'Edward Newgate' produces.
    """
    translated = ALIASES.get(name, name)
    return norm_name(translated.split("/")[0].strip())


def fill_missing(target, source):
    """Copy fields from source into target where target has nothing."""
    for field in ("bounty", "crew", "job", "devil_fruit", "image"):
        if not target.get(field) and source.get(field):
            target[field] = source[field]
    if target.get("status") == "unknown" and source.get("status"):
        target["status"] = source["status"]


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
    """Return {normalised requested name: thumbnail URL} from the One Piece Wiki.

    Asks for the page image (usually the infobox portrait) for each name,
    50 titles per request. Names with no wiki page simply come back missing.
    Requested titles are resolved through the API's normalized/redirect
    info, so a request for 'Marshall D. Teach' correctly maps to the
    'Blackbeard' page's image.
    """
    found = {}
    names = sorted(set(n for n in names if n))
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
        query = data.get("query", {}) or {}
        pages = query.get("pages", {}) or {}
        # Resolve each requested title to the page it ended up on.
        resolved = {}
        for norm in query.get("normalized", []) or []:
            resolved[norm["from"]] = norm["to"]
        for red in query.get("redirects", []) or []:
            resolved[red["from"]] = red["to"]
        by_title = {p.get("title"): p for p in pages.values()}
        for req in batch:
            final = req
            for _ in range(3):  # follow normalisation, then redirect
                final = resolved.get(final, final)
            page = by_title.get(final)
            if not page or page.get("missing") is not None:
                continue
            thumb = (page.get("thumbnail") or {}).get("source")
            if thumb:
                found[norm_name(req)] = thumb
        time.sleep(0.3)  # be polite to a free community wiki
    return found


def fetch_fandom_images_by_search(queries):
    """Find wiki portraits by searching, for names the direct lookup missed.

    queries: {record key: search text}. Takes the top search hit, but only
    when the hit's title shares a word with the search text (guards against
    the search returning an unrelated page). Returns {record key: thumbnail}.
    """
    found = {}
    for key, text in queries.items():
        data = fetch_json(FANDOM_API, {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": text,
            "srnamespace": 0,
            "srlimit": 3,
        })
        hits = (data.get("query", {}) or {}).get("search", []) or []
        if hits:
            title = hits[0].get("title", "")
            # Sanity check: the hit must share a word (3+ letters) with the query.
            q_words = {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}
            t_words = {w for w in re.split(r"[^a-z0-9]+", title.lower()) if len(w) > 2}
            if q_words & t_words:
                page = fetch_json(FANDOM_API, {
                    "action": "query",
                    "format": "json",
                    "prop": "pageimages",
                    "piprop": "thumbnail",
                    "pithumbsize": 400,
                    "titles": title,
                })
                for p in (page.get("query", {}) or {}).get("pages", {}).values():
                    thumb = (p.get("thumbnail") or {}).get("source")
                    if thumb:
                        found[key] = thumb
        time.sleep(0.2)
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

    # --- Index source 2 by canonical key ---
    op_by_name = {}
    for c in op:
        name = (c.get("name") or {}).get("en") or ""
        key = match_key(name)
        if key and key not in op_by_name:
            op_by_name[key] = c

    # --- Merge, starting from source 1 (richer structured data) ---
    merged = {}
    matched = 0
    for c in ap:
        name = c.get("name") or ""
        key = match_key(name)
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
        if key in merged:
            # Two source rows for the same character ('Im Sama' and
            # 'Imu Neronna'): keep the first name, fill any gaps.
            fill_missing(merged[key], rec)
        else:
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

    # --- Pass 2: aliases, then wiki search, for portraits the direct lookup missed ---
    # 2a. Known French -> English name aliases (api-onepiece.com uses French names).
    alias_by_key = {match_key(k): v for k, v in ALIASES.items()}
    alias_titles = {key: alias_by_key[key] for key in merged
                    if not merged[key]["image"] and key in alias_by_key}
    alias_images = fetch_fandom_images(list(alias_titles.values()))
    recovered_alias = 0
    for key, title in alias_titles.items():
        url = alias_images.get(norm_name(title))
        if url:
            merged[key]["image"] = url
            recovered_alias += 1
    print(f"wiki alias pass: recovered {recovered_alias} portraits")
    # 2b. Wiki search with the name before any '/'.
    # Some data names are French ('Edward Newgate / Barbe Blanche'), so the
    # search uses the name before any '/'.
    missing = {key: rec["name"].split("/")[0].strip()
               for key, rec in merged.items() if not rec["image"]}
    extra = fetch_fandom_images_by_search(missing)
    for key, url in extra.items():
        merged[key]["image"] = url
    print(f"wiki search pass: recovered {len(extra)} more portraits "
          f"({len(missing) - len(extra)} still without one)")

    # --- Drop the obscure ones: no image, no bounty, no Devil Fruit ---
    kept, dropped = [], []
    for rec in merged.values():
        if not rec["image"] and not rec["bounty"] and not rec["devil_fruit"]:
            dropped.append(rec["name"])
        else:
            kept.append(rec)
    print(f"dropped {len(dropped)} obscure characters "
          f"(no image, no bounty, no Devil Fruit): {', '.join(dropped[:15])}"
          + (" ..." if len(dropped) > 15 else ""))

    records = sorted(kept, key=lambda r: r["name"].lower())
    with open("characters.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))

    with_images = sum(1 for r in records if r["image"])
    from_wiki = sum(1 for r in records if r["image"] and "wikia.nocookie.net" in r["image"])
    with_fruit = sum(1 for r in records if r["devil_fruit"])
    print(f"merged: {len(records)} characters "
          f"({matched} in both APIs, {only_op} only in onepieceapi.com)")
    print(f"with image: {with_images} ({from_wiki} from the wiki), "
          f"with Devil Fruit: {with_fruit}")
    for hero in ("Monkey D Luffy", "Roronoa Zoro", "Nami", "Sanji", "Alvero",
                 "Edward Newgate / Barbe Blanche",
                 "Charlotte Linlin / Big Mom",
                 "Marchall D. Teach / Barbe Noire", "Eustass Kidd",
                 "Don Quijote Doflamingo"):
        hit = [r for r in records if r["name"] == hero]
        print(hero, "->", json.dumps(hit[0]) if hit else "NOT FOUND")


if __name__ == "__main__":
    main()
