# One Piece Character Explorer

A small web app to search and explore One Piece characters.

## Data

Character data is merged from two free public APIs, keeping only the important fields from each:

- **Name, image, status, affiliation, bounties** — from [onepieceapi.com](https://onepieceapi.com)
- **Bounty, crew, job, Devil Fruit** — from [api-onepiece.com](https://api.api-onepiece.com)

The merged data lives in `characters.json`, so the page works without live API calls.

## Stack

Plain HTML, CSS, and JavaScript. No backend, no build step.

## Run it

Open `index.html` in a browser.

## Plan

1. Repo + README (this step)
2. Page skeleton — search box, filters, results grid
3. Merge script — fetch both APIs, keep only the important fields, write `characters.json`
4. Show characters as cards
5. Search by name
6. Crew and status filters
7. Character detail view
8. Styling polish
