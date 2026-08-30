# Visual Polish Report

Date: 2026-08-30

## About Us

### Before

- The page checked for `static/images/remas.jpg`, which did not exist.
- The missing portrait produced a visible “Remas photo placeholder”.
- The page exposed technical portfolio cards such as Technologies, PostgreSQL/SQLite, data processing, and system design.
- The content order did not match the intended personal narrative.

### Problems

- Missing founder image and visible placeholder.
- About content read partly like technical documentation.
- The live iframe had no durable visual fallback.
- No clear personal-message section.

### Changes

- Removed the `remas.jpg` lookup and all founder-photo placeholder markup from the rendered page.
- Added a non-person abstract hero illustration representing healthcare, data, and AI.
- Reorganized the page into exactly seven sections: Hero, story, what SymptoSense is, why it matters, project showcase, Remas's message, and final CTA.
- Removed Technologies and implementation-detail sections from About Us only.
- Reused the existing approved Arabic and English personal copy rather than inventing a biography.
- Kept `/about-us` as the independent page and `/about` as its redirect alias.

## Images

### Added

- `static/images/about-hero.webp` — 960×960, 25 KB.
- `static/images/about-story.webp` — 1100×880, 30 KB.
- `static/images/symptosense-social-preview.png` — 1200×630, 183 KB.

The two About illustrations and the social-preview background were generated for this project with the built-in image generator, then resized and optimized for web delivery. They contain no people, fake founder portrait, health records, email addresses, tokens, logs, or user data.

### Retained

- `icons/about-us-phone.webp` remains the original project visual and is used as the iframe fallback.

### Removed from rendered UI

- `remas.jpg` dependency.
- Remas photo placeholder.
- Broken-image fallback placeholder.

## Real Project Showcase

- The same-origin `/home` iframe remains the live project preview.
- The original `icons/about-us-phone.webp` project visual is displayed underneath it and remains visible unless the iframe contains a valid rendered page.
- A new Production screenshot could not be captured: the published Railway URL timed out in the available browser, and local-file navigation was blocked by browser security policy. The fallback is therefore an original project illustration, not a newly captured Production screenshot.

## Social Preview

- `og:image`: `${SITE_URL}/static/images/symptosense-social-preview.png`
- Dimensions: 1200×630.
- Added `og:title`, `og:description`, `og:image`, image dimensions, image alt, `og:url`, `og:type`, and site name.
- Added `twitter:card=summary_large_image`, title, description, and image.
- Production URLs continue to come from the existing `_site_url()` behavior; no deployment domain was hard-coded into authentication or application logic.

## README

### Broken references found

- `architecture_diagram.svg`
- `MODEL_CARD.md`

### Fixed

- Added a simple SVG diagram matching the actual Flask, authentication, analysis, search/medications, knowledge-base, database, and protected Admin paths.
- Added a concise Model Card based only on `train_model.py` and the exported `ml_model.json` metadata.
- Corrected README model counts to 18 classes and 15 features and clarified that 65.28% is internal synthetic-data test accuracy, not clinical accuracy.
- Automated README-link audit now reports no missing relative files.

## Responsive

- Mobile CSS stacks Hero content naturally, collapses purpose cards, reduces device-frame padding, and keeps the CTA full-width.
- Tablet CSS switches all split sections to one column.
- Desktop retains balanced text/visual splits and a constrained laptop mockup.
- Source-level and route tests passed. Pixel-level browser screenshots at 375, 390, 768, and 1024 px were not available because the browser could not load the deployed site.

## Accessibility

- Meaningful illustrations have bilingual descriptive alt text.
- The decorative concept and message mark are hidden from assistive technology.
- Image dimensions are declared to reduce layout shift.
- Non-Hero images use lazy loading.
- Motion remains subtle and is disabled with `prefers-reduced-motion`.

## Testing

- 25 automated tests passed.
- `/about-us` returns 200 in Arabic and English.
- `/about` redirects to `/about-us`.
- All three new assets return successfully through Flask.
- No `remas.jpg`, visible photo placeholder, Technologies section, or PostgreSQL/SQLite section is rendered on About Us.
- OG and Twitter metadata are present with absolute URLs in rendered pages.
- README relative links resolve to existing files.
- Existing Authentication, Admin, database, medical knowledge, search, medication, and API tests remain green.

## Remaining Issues

- Railway was not deployed or restarted from this workspace.
- LinkedIn, WhatsApp, and X crawler caches were not refreshed against a deployed build.
- A newly captured Production website screenshot was not obtained. The live iframe has an original project-visual fallback, but this does not satisfy a strict requirement for a new real screenshot.
- Visual testing at the requested exact viewport widths was not completed in a real browser.
