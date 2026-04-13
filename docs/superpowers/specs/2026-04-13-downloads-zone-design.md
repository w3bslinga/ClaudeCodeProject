# Downloads Zone — Design Spec

## Overview
A new page (`downloads.html`) where users can download Alwin's apps for macOS, Windows, Android, and iOS. Not listed in navigation for now. Matches the existing site's dark theme.

## Inspiration
Obsidian's download page (https://obsidian.md/download) — single product hero with per-platform download buttons.

## File Hosting
App binaries (`.apk`, `.exe`, `.dmg`) are hosted as **GitHub Release assets** on each app's repo. Download buttons link directly to release asset URLs. iOS links will point to the App Store once available.

Example URL pattern:
```
https://github.com/<username>/<app-repo>/releases/download/v1.0.0/<filename>
```

## Page Structure

### 1. Header
- Title: "Downloads"
- Subtitle: "Apps built by Alwin"

### 2. App Cards
One card per app. First app: **Calculator**.

Each card contains:
- **App icon** — placeholder emoji or image to start
- **App name** — e.g. "Calculator"
- **Description** — one line, e.g. "A simple calculator built with Python & Kivy"
- **Platform buttons row** — four buttons in order: macOS | Windows | Android | iOS

### 3. Footer
- Small text: "More apps coming soon"

## Platform Button States

### Ready (download available)
- Clickable, site accent color
- OS logo icon + OS name label
- Links directly to GitHub Release asset (or App Store URL for iOS)

### Coming Soon (no build yet)
- Greyed out, reduced opacity, non-clickable
- Shows "Coming Soon" on hover via tooltip

## Button Order
macOS | Windows | Android | iOS (desktop first, mobile second)

## Styling
- Matches existing dark theme from `style.css`
- Same fonts, colors, and spacing as other pages
- No hamburger nav listing (page is unlisted for now)
- Hamburger menu still present on the page for consistency

## Tech Stack
- Static HTML + CSS (inline or in `style.css`)
- No JavaScript required beyond existing nav drawer logic
- App built with Python + Kivy + Buildozer

## Future Scaling
- To add a new app: duplicate the card HTML, update icon/name/description/links
- To add store links: swap GitHub Release URL for store URL, update button style if desired
- To list in nav: add entry to hamburger menu across all pages
