[Full ONS Design System docs](https://service-manual.ons.gov.uk/design-system)

# Frontend UI Architecture

This document describes how this repository currently uses the ONS Design System on branch
`MS04/extra-pages`.

The key source files are:

- `data_explorer/templates/base.html`
- `data_explorer/templates/components/header/header.html`
- `data_explorer/templates/components/footer/footer.html`
- `data_explorer/static/js/tabs.js`
- `data_explorer/services/search_data.py`
- `data_explorer/services/search_service.py`

We pin the Design System to `73.0.3`. If you upgrade, update all DS references together
(CSS, JS, and `ONS_assets_base_URL`) and regression test tabs/navigation journeys.

## 1) Base template contract

`base.html` is the shared layout for the current main site pages. It provides:

- Head assets:
  - Tailwind CSS `2.2.19`
  - ONS DS CSS `73.0.3`
  - Font Awesome `4.4.0`
  - Local `static/css/styles.css`
  - Global `ONS_assets_base_URL`
  - ONS DS JS `73.0.3` (deferred)
- Body structure:
  - skip link
  - shared header include
  - `<main id="main-content">` wrapper
  - shared footer include
  - global `static/js/tabs.js`

`base.html` exposes these blocks:

- `head_extra` for page-specific CSS/JS in `<head>`
- `content` for page body content
- `scripts` for page-specific scripts at the end of `<body>`

## 2) Templates extending `base.html`

Examples of how files extend `base.html` can be seen in the following:

- `data_explorer/templates/index.html`
- `data_explorer/templates/about.html`
- `data_explorer/templates/framework.html`
- `data_explorer/templates/resources.html`
- `data_explorer/templates/faqs.html`
- `data_explorer/templates/terms.html`
- `data_explorer/templates/r_package.html`
- `data_explorer/templates/search.html`
- `data_explorer/templates/indicator_calculators.html`
- `data_explorer/templates/coming_soon.html`

Legacy/standalone templates still exist (for example `data_explorer/templates/data_explorer.html`,
`data_explorer/templates/data_plots.html`, `data_explorer/templates/login.html`, older form pages)
and do not all inherit from `base.html`.

For new user-facing pages, default to extending `base.html`.

## 3) Route map relevant to templates

Current page routes are split across two blueprints:

- `main_bp` in `data_explorer/routes/main_routes.py`:
  - `/`, `/about`, `/resources`, `/faqs`, `/terms`, `/search`, `/r_package`, `/version`
- `data_bp` in `data_explorer/routes/data_routes.py`:
  - `/framework`, `/indicator_calculators`, `/data_explorer`, `/data_plots`, plus API/data routes

Important branch difference: `/resources` and `/faqs` now render their own templates directly,
not `coming_soon`.

## 4) Shared component and macro usage

### Layout/components

- Header: `data_explorer/templates/components/header/header.html`
- Footer: `data_explorer/templates/components/footer/footer.html`
- Indicator info banner: `data_explorer/templates/components/indicator_banner.html`

Route-level hash allowlists are defined in `data_explorer/routes/data_routes.py` and injected into
templates via context processor keys:

- `allowed_framework_hashes`
- `allowed_indicator_calculator_hashes`

These are now used by `header.html` to show only the allowed framework and indicator links.
`ENABLE_FULL_UI` still controls other template blocks (for example cards/search visibility), but
tab/link allowlisting is centralized in the route layer.

### Common macros

Under `data_explorer/templates/macros`:

- Form controls: `input.html`, `select.html`, `radios.html`, `upload.html`
- Data display: `table.html`, `publications_list.html`, `timeline.html`
- Structure/navigation: `accordion.html`, `framework_section.html`, `cards.html`
- Links/buttons/media: `external_link.html`, `buttons.html`, `image.html`, `slideshow.html`

`timeline.html` supports highlighted content by passing mapping values with `highlight: True`
for `heading`, `subheading`, or `list_items`, which adds class `timeline--highlight`.

## 5) Tabs and hash navigation behavior

Global behavior is in `data_explorer/static/js/tabs.js`.

- Route-specific tab maps/default inner tabs are used for:
  - `/framework`
  - `/indicator_calculators`
- Subtab links (`.subtab`) are intercepted on same-page clicks, then tab state is applied via hash.
- ONS tabs (`.ons-tab`) are activated by hash using `activateOnsTabByHash`.
- Header/footer cross-page hash links are intercepted and stored in `sessionStorage`
  (`pendingHash`, `pendingPath`), then applied after navigation.
- Hash state is restored on load and hash changes are re-applied.

### Hash allowlist and redirects

- `framework.html` and `indicator_calculators.html` expose:
  - `window.allowedFrameworkHashes`
  - `window.comingSoonUrl`
  - `window.enforceHashAllowlist`
- In `tabs.js`, `enforceAllowedFrameworkHash(...)` redirects to `coming soon` when a hash is not
  allowed.
- Inner hash panels (for example `#wildfires-select-file`) are allowed when their parent
  `.subtab-content` hash is allowed.
- When `ENABLE_FULL_UI` is true, `window.enforceHashAllowlist` is false, so redirects are disabled.
- When there is no URL hash, tabs default to the first allowed top-level subtab.

This is why tab behavior is consistent for header/footer hash navigation and subtab links, while
generic body links without the expected classes may behave differently unless they resolve through
the hash activation flow.

## 6) Search service alignment

Search uses:

- Data source: `data_explorer/services/search_data.py` (`get_search_entries`)
- Ranking: `data_explorer/services/search_service.py` (RapidFuzz `WRatio`)

Current indexed pages include `FAQs` (`/faqs`), `R Package` (`/r_package`), `Terms and conditions`
(`/terms`), `Resources` (`/resources`), and framework/indicator sections.

Search ranking flow:

1. Build a single searchable string from `title + summary + keywords`.
2. Fuzzy match query with `score_cutoff=60`, `limit=10`.
3. Sort by score descending, then by title for tie stability.

## 7) Styling guidance in this codebase

- Prefer ONS layout/type utilities (`ons-grid`, `ons-u-*`) for structure and spacing.
- Use `ons-panel ons-panel--info ons-panel--no-title` for informational callouts.
- Keep custom overrides in `data_explorer/static/css/styles.css`.
- Use Tailwind utilities only where needed for local layout adjustments.

## 8) Maintenance checklist

- [ ] DS version is consistent in CSS, JS, and `ONS_assets_base_URL`.
- [ ] New pages extend `base.html` unless there is a documented reason not to.
- [ ] Shared navigation, hash tabs, and header/footer journeys still work after template changes.
- [ ] Search entries are updated when new user-facing pages/sections are added.
- [ ] LIVE/DEV hash allowlists in `data_routes.py` match intended visibility for each route.
- [ ] Hash redirects only run when `window.enforceHashAllowlist` is true.
- [ ] Macros are reused instead of duplicating ONS markup patterns.
