# One Piece Character Explorer

A small web app to search and explore One Piece characters.

## Data

Character data is merged from three free public sources, keeping only the important fields from each:

- **Portraits** — from the [One Piece Wiki](https://onepiece.fandom.com) (official anime/manga art)
- **Bounty, crew, job, Devil Fruit** — from [api-onepiece.com](https://api.api-onepiece.com)
- **Affiliation, bounties, extra characters** — from [onepieceapi.com](https://onepieceapi.com)

The merged data lives in `characters.json`, so the page works without live API calls. Run `merge.py` to refresh it. Characters left with no portrait, no bounty and no Devil Fruit are left out — they're minor names with nothing to show. Characters listed under two names (French in one source, English in the other) are merged into one card.

## Stack

Plain HTML, CSS, and JavaScript. No backend, no build step.

## Run it

Open `index.html` in a browser (through a local server or GitHub Pages, so `characters.json` can load).

## Plan

1. Repo + README (this step)
2. Page skeleton — search box, filters, results grid
3. Merge script — fetch the sources, keep only the important fields, write `characters.json`
4. Show characters as cards
5. Search by name
6. Crew and status filters
7. Character detail view
8. Styling polish
