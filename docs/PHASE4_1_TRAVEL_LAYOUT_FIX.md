# Phase 4.1 — Travel layout correction

## Problem

The Airport Information card used `grid-row: span 2`. CSS Grid stretched that
card to the combined height of the Hotel Information and Things To Do cards,
leaving a large blank area beneath the airport content.

## Correction

- Airport Information now spans both columns, not two rows.
- Hotel Information and Things To Do sit side by side at their natural heights.
- Favorite Restaurants remains full width.
- Grid items align to the start instead of stretching vertically.
- The existing single-column mobile layout is preserved.

No routes, data, database tables, or JavaScript behavior changed.
