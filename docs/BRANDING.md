# Carrera Branding

## Name

**Carrera** — from the Spanish/Portuguese for "career" (and, by happy coincidence, "race"). It's short, memorable, and captures both the professional ambition and the forward-motion of a job search.

Pronounced *cah-RARE-uh*. Always capitalized. No alternate spellings (not "Carrerra", "Karrera", etc.).

## Logo

The mark is an open **C** with a forward arrow in its mouth — a career in motion.

| File | Use |
|---|---|
| `assets/logo-mark.svg` | The icon alone (128×128, scalable) |
| `assets/logo.svg` | Full horizontal lock-up, light background |
| `assets/logo-dark.svg` | Full lock-up, dark background |
| `assets/icon.ico` | Windows executable icon (multi-res 16→256) |
| `assets/icon-256.png` | Raster fallback, 256×256 |
| `frontend/public/favicon.svg` | Browser favicon |

### Clear space

Keep at least the width of the arrow's shaft of clear space around the mark on every side. The mark should never be smaller than 20 px square in a UI (below that, legibility breaks).

### Don'ts

- Don't recolor the mark outside the palette below.
- Don't stretch, skew, or add drop shadows.
- Don't place the light mark on a light background or the dark mark on a dark one — always pair.

## Color palette

The primary hue is a **deep teal** (career / growth / stability), accented by a **warm amber** (energy / action). Neutrals are the standard Tailwind `slate` scale.

### Primary — Teal

| Token | Hex | Use |
|---|---|---|
| `carrera-50` | `#F0FDFA` | Lightest tint, subtle highlight backgrounds |
| `carrera-100` | `#CCFBF1` | Hover tints in light mode |
| `carrera-500` | `#14B8A6` | Dark-mode primary, active states |
| `carrera-600` | `#0D9488` | **Primary** — buttons, links, active nav, logo |
| `carrera-700` | `#0F766E` | Hover, pressed |
| `carrera-900` | `#134E4A` | Deep surfaces, focus rings on light bg |

### Accent — Amber

| Token | Hex | Use |
|---|---|---|
| `accent-400` | `#FBBF24` | **Accent** — arrow in logo, "hot match" badges, emphasis highlights |
| `accent-500` | `#F59E0B` | Hover on accent CTAs |
| `accent-600` | `#D97706` | Pressed accent |

### Semantic

| Purpose | Color | Hex |
|---|---|---|
| Success (strong match, offers) | emerald-500 | `#10B981` |
| Warning (needs attention) | amber-500 | `#F59E0B` |
| Error (scrape failed, API error) | red-500 | `#EF4444` |
| Info (neutral badges) | slate-500 | `#64748B` |

### Neutrals

Standard Tailwind `slate`. Text uses `slate-900` (light) / `slate-100` (dark); borders `slate-200` / `slate-700`; card surfaces `white` / `slate-800`.

## Typography

**UI:** Inter via system fallback — `Inter, "Segoe UI", system-ui, -apple-system, sans-serif`.
**Mono:** `ui-monospace, "JetBrains Mono", Consolas, monospace` (used for cron strings, URLs, code blocks).

Sizes follow Tailwind's default scale. Headings are `font-bold` (700), body is `font-normal` (400), labels are `font-medium` (500) and uppercase with `tracking-wide`.

## Voice

- **Direct**: "Fetch jobs", not "Let Carrera help you discover new opportunities".
- **Brazilian-savvy**: location names, timezones, and currency default to BR conventions where applicable.
- **Honest about costs**: always surface AI token pricing before a paid call runs.
