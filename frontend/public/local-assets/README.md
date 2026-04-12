# Local assets

This folder stores strictly local image assets for offline UI rendering.

- `placeholder.jpg`: default fallback used by Wiki-Voz cards when an entry has no valid local image.

## Runtime usage

- `WikiVozScreen.jsx` uses this placeholder for missing/invalid image URLs.
- `CulturalTermPopup.jsx` also falls back safely to local imagery when API-provided media is unavailable.

## Why this exists

- Keeps card rendering stable in offline/LAN-only demos.
- Prevents broken image icon clutter in dense masonry layouts.
