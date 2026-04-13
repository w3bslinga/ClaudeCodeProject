# Downloads Zone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Downloads Zone page where users can download Alwin's apps per platform, styled like Obsidian's download page and matching the existing dark theme.

**Architecture:** Single static HTML page (`downloads.html`) following the same self-contained pattern as `chill-zone.html` — inline `<style>`, same CSS variables, same nav drawer/theme toggle/cursor effects. One app card component with platform download buttons. No new dependencies.

**Tech Stack:** HTML, CSS (inline), vanilla JS (nav + theme toggle — copied from existing pages)

---

### Task 1: Create downloads.html with boilerplate + nav + theme toggle

**Files:**
- Create: `downloads.html`

This task creates the full page shell by copying the proven pattern from `chill-zone.html`: head, CSS variables, theme toggle, home button, hamburger nav drawer, theme JS, and cursor effects.

- [ ] **Step 1: Create `downloads.html` with full boilerplate**

Create `downloads.html` with the following content. This is the complete page shell — header, nav drawer, theme toggle, and placeholder content area. All CSS is inline following the existing pattern.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Downloads — Alwin Thomas</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #f9f9f8;
      --surface: #ffffff;
      --text: #1a1a1a;
      --muted: #6b7280;
      --border: #e5e7eb;
      --accent: #0a66c2;
      --accent-hover: #0854a5;
      --radius: 16px;
      --shadow: 0 4px 24px rgba(0,0,0,0.07);
      --toggle-bg: #e5e7eb;
      --toggle-hover: #d1d5db;
    }
    [data-theme="dark"] {
      --bg: #111111;
      --surface: #1c1c1c;
      --text: #f0ede8;
      --muted: #9ca3af;
      --border: #2e2e2e;
      --shadow: 0 4px 24px rgba(0,0,0,0.45);
      --toggle-bg: #2e2e2e;
      --toggle-hover: #3a3a3a;
    }

    html { transition: background 0.2s, color 0.2s; overflow-x: hidden; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 2rem 1rem 4rem;
      line-height: 1.6;
      transition: background 0.2s, color 0.2s;
      overflow-x: hidden;
      width: 100%;
    }

    /* ── Theme toggle ── */
    .theme-toggle {
      position: fixed;
      top: 1.1rem;
      right: 1.1rem;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      border: none;
      background: var(--toggle-bg);
      color: var(--text);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s, transform 0.1s;
      z-index: 100;
    }
    .theme-toggle:hover { background: var(--toggle-hover); }
    .theme-toggle:active { transform: scale(0.92); }
    .theme-toggle .icon-sun,
    .theme-toggle .icon-moon {
      position: absolute;
      transition: opacity 0.2s, transform 0.2s;
    }
    .theme-toggle .icon-moon { opacity: 0; transform: rotate(-30deg) scale(0.8); }
    [data-theme="dark"] .theme-toggle .icon-sun { opacity: 0; transform: rotate(30deg) scale(0.8); }
    [data-theme="dark"] .theme-toggle .icon-moon { opacity: 1; transform: rotate(0deg) scale(1); }

    /* ── Navigation (hamburger + home) ── */
    .home-btn {
      position: fixed;
      top: 1.1rem;
      left: 1.1rem;
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      color: var(--text);
      background: rgba(255,255,255,0.25);
      border: 1.5px solid var(--border);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
      z-index: 100;
      box-shadow: 0 2px 12px rgba(0,0,0,0.12);
    }
    [data-theme="dark"] .home-btn { background: rgba(30,30,30,0.45); }
    .home-btn:hover { transform: scale(1.07); box-shadow: 0 4px 16px rgba(0,0,0,0.18); }

    .hamburger {
      position: fixed;
      top: 3.8rem;
      left: 1.1rem;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      border: none;
      background: var(--toggle-bg);
      color: var(--text);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
      z-index: 200;
    }
    .hamburger:hover { background: var(--toggle-hover); }

    .nav-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.4);
      z-index: 300;
    }
    .nav-overlay.open { display: block; }

    .nav-drawer {
      position: fixed;
      top: 0; left: 0;
      width: 260px;
      height: 100%;
      background: var(--surface);
      border-right: 1px solid var(--border);
      box-shadow: 4px 0 24px rgba(0,0,0,0.15);
      transform: translateX(-100%);
      transition: transform 0.25s cubic-bezier(0.4,0,0.2,1);
      z-index: 400;
      display: flex;
      flex-direction: column;
      padding: 1.25rem 1rem;
    }
    .nav-drawer.open { transform: translateX(0); }

    .nav-drawer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    .nav-drawer-title {
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .nav-close {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      border: none;
      background: transparent;
      color: var(--text);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
    }
    .nav-close:hover { background: var(--toggle-bg); }

    .nav-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
    .nav-item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.6rem 0.75rem;
      border-radius: 8px;
      text-decoration: none;
      font-size: 0.92rem;
      font-weight: 500;
      color: var(--text);
      transition: background 0.15s, color 0.15s;
    }
    .nav-item:hover { background: var(--toggle-bg); color: var(--accent); }

    /* ── Page content ── */
    .page-wrap {
      max-width: 680px;
      width: 100%;
      margin-top: 1rem;
      text-align: center;
    }

    .page-title {
      font-size: 2rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin-bottom: 0.25rem;
    }
    .page-subtitle {
      font-size: 0.95rem;
      color: var(--muted);
      margin-top: 0.3rem;
      margin-bottom: 2.5rem;
    }

    /* ── App card ── */
    .app-card {
      background: var(--surface);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      border: 1.5px solid var(--border);
      padding: 2.5rem 2rem;
      text-align: center;
      margin-bottom: 2rem;
    }
    .app-icon {
      font-size: 3rem;
      margin-bottom: 0.75rem;
    }
    .app-name {
      font-size: 1.4rem;
      font-weight: 700;
      margin-bottom: 0.3rem;
    }
    .app-desc {
      font-size: 0.92rem;
      color: var(--muted);
      margin-bottom: 1.5rem;
    }

    /* ── Platform buttons ── */
    .platform-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: center;
    }
    .platform-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.65rem 1.25rem;
      border-radius: 10px;
      border: 1.5px solid var(--border);
      background: var(--surface);
      color: var(--text);
      font-size: 0.88rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s, transform 0.1s;
    }
    .platform-btn:hover {
      border-color: var(--accent);
      color: var(--accent);
      transform: translateY(-1px);
    }
    .platform-btn:active { transform: scale(0.97); }

    .platform-btn.coming-soon {
      opacity: 0.4;
      cursor: default;
      pointer-events: none;
      position: relative;
    }
    .platform-btn.coming-soon:hover {
      border-color: var(--border);
      color: var(--text);
      transform: none;
    }

    /* Tooltip for coming-soon buttons (enabled via JS pointer-events workaround) */
    .platform-btn-wrap { position: relative; display: inline-flex; }
    .platform-btn-wrap .tooltip {
      display: none;
      position: absolute;
      bottom: calc(100% + 8px);
      left: 50%;
      transform: translateX(-50%);
      background: var(--text);
      color: var(--bg);
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.3rem 0.6rem;
      border-radius: 6px;
      white-space: nowrap;
      pointer-events: none;
    }
    .platform-btn-wrap:hover .tooltip { display: block; }

    /* ── Footer ── */
    .page-footer {
      text-align: center;
      font-size: 0.82rem;
      color: var(--muted);
      margin-top: 1rem;
    }

    /* ── Star cursor ── */
    #star-cursor {
      position: fixed;
      width: 22px; height: 22px;
      pointer-events: none;
      z-index: 9999;
      transform: translate(-50%,-50%);
      opacity: 1;
      transition: opacity 0.2s;
    }
    #star-cursor svg { width: 100%; height: 100%; }
    #star-cursor.spinning svg { animation: spin 0.4s linear; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .trail-particle {
      position: fixed;
      border-radius: 50%;
      pointer-events: none;
      z-index: 9998;
      animation: fadeTrail 0.6s ease-out forwards;
      transform: translate(-50%,-50%);
    }
    @keyframes fadeTrail { to { opacity: 0; transform: translate(-50%,-50%) scale(0.2); } }

    /* ── Responsive ── */
    @media (max-width: 500px) {
      .platform-buttons { flex-direction: column; align-items: center; }
      .platform-btn { width: 100%; justify-content: center; }
    }
  </style>
</head>
<body>

  <!-- Home button -->
  <a class="home-btn" style="cursor:pointer" onclick="window.location.href='index.html'" aria-label="Go to home">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  </a>

  <!-- Hamburger -->
  <button class="hamburger" id="hamburger" aria-label="Open menu" aria-expanded="false">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <line x1="3" y1="6" x2="21" y2="6"/>
      <line x1="3" y1="12" x2="21" y2="12"/>
      <line x1="3" y1="18" x2="21" y2="18"/>
    </svg>
  </button>

  <!-- Nav drawer -->
  <div class="nav-overlay" id="nav-overlay"></div>
  <nav class="nav-drawer" id="nav-drawer" aria-hidden="true">
    <div class="nav-drawer-header">
      <span class="nav-drawer-title">Pages</span>
      <button class="nav-close" id="nav-close" aria-label="Close menu">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <ul class="nav-list">
      <li><a class="nav-item" style="cursor:pointer" onclick="window.location.href='index.html'">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
          <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        Home
      </a></li>
      <li><a class="nav-item" style="cursor:pointer" onclick="window.location.href='skill-zone.html'">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        Skill Zone
      </a></li>
      <li><a class="nav-item" style="cursor:pointer" onclick="window.location.href='chill-zone.html'">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M6 12h4m-2-2v4m5-3h.01M17 11h.01"/><rect x="2" y="6" width="20" height="12" rx="2"/>
        </svg>
        Chill Zone
      </a></li>
      <li><a class="nav-item" style="cursor:pointer" onclick="window.location.href='architecture.html'">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v3"/>
        </svg>
        Architecture
      </a></li>
    </ul>
  </nav>

  <!-- Theme toggle -->
  <button class="theme-toggle" id="theme-toggle" aria-label="Toggle dark mode">
    <svg class="icon-sun" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
    <svg class="icon-moon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  </button>

  <!-- Page content -->
  <div class="page-wrap">
    <h1 class="page-title">Downloads</h1>
    <p class="page-subtitle">Apps built by Alwin</p>

    <!-- Calculator app card -->
    <div class="app-card">
      <div class="app-icon">🧮</div>
      <h2 class="app-name">Calculator</h2>
      <p class="app-desc">A simple calculator built with Python &amp; Kivy</p>

      <div class="platform-buttons">
        <!-- macOS — Coming Soon -->
        <span class="platform-btn-wrap">
          <span class="tooltip">Coming Soon</span>
          <span class="platform-btn coming-soon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
            macOS
          </span>
        </span>

        <!-- Windows — Coming Soon -->
        <span class="platform-btn-wrap">
          <span class="tooltip">Coming Soon</span>
          <span class="platform-btn coming-soon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>
            Windows
          </span>
        </span>

        <!-- Android — Coming Soon -->
        <span class="platform-btn-wrap">
          <span class="tooltip">Coming Soon</span>
          <span class="platform-btn coming-soon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.523 15.341a1 1 0 0 0 1-1v-5.4a1 1 0 0 0-2 0v5.4a1 1 0 0 0 1 1m-11.046 0a1 1 0 0 0 1-1v-5.4a1 1 0 0 0-2 0v5.4a1 1 0 0 0 1 1m11.405-8.665 1.406-2.433a.292.292 0 1 0-.506-.292l-1.424 2.464A8.714 8.714 0 0 0 12 5.2a8.714 8.714 0 0 0-5.358 1.215L5.218 3.951a.292.292 0 0 0-.506.292l1.406 2.433C3.37 8.19 1.378 11.244 1.378 14.807h21.244c0-3.563-1.992-6.617-4.74-8.131M8.5 11.658a.95.95 0 1 1 0-1.9.95.95 0 0 1 0 1.9m7 0a.95.95 0 1 1 0-1.9.95.95 0 0 1 0 1.9"/></svg>
            Android
          </span>
        </span>

        <!-- iOS — Coming Soon -->
        <span class="platform-btn-wrap">
          <span class="tooltip">Coming Soon</span>
          <span class="platform-btn coming-soon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
            iOS
          </span>
        </span>
      </div>
    </div>

    <p class="page-footer">More apps coming soon</p>
  </div>

  <script>
    // ── Navigation ─────────────────────────────────────────────────
    const hamburgerBtn = document.getElementById('hamburger');
    const navDrawer    = document.getElementById('nav-drawer');
    const navOverlay   = document.getElementById('nav-overlay');
    const navClose     = document.getElementById('nav-close');

    function openNav() { navDrawer.classList.add('open'); navOverlay.classList.add('open'); hamburgerBtn.setAttribute('aria-expanded','true'); navDrawer.setAttribute('aria-hidden','false'); }
    function closeNav() { navDrawer.classList.remove('open'); navOverlay.classList.remove('open'); hamburgerBtn.setAttribute('aria-expanded','false'); navDrawer.setAttribute('aria-hidden','true'); }
    hamburgerBtn.addEventListener('click', openNav);
    navClose.addEventListener('click', closeNav);
    navOverlay.addEventListener('click', closeNav);

    // ── Theme ──────────────────────────────────────────────────────
    const root = document.documentElement;
    const toggleBtn = document.getElementById('theme-toggle');
    const saved = localStorage.getItem('theme');
    if (saved) root.setAttribute('data-theme', saved);
    else if (window.matchMedia('(prefers-color-scheme: dark)').matches) root.setAttribute('data-theme', 'dark');
    toggleBtn.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });

    // ── Star cursor + Particle trail ──────────────────────────
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      const darkColors  = ['#818cf8','#38bdf8','#34d399','#f472b6','#fb923c'];
      const lightColors = ['#6366f1','#0ea5e9','#10b981','#ec4899','#f97316'];
      const star = document.createElement('div');
      star.id = 'star-cursor';
      star.innerHTML = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2 L13.5 10.5 L22 12 L13.5 13.5 L12 22 L10.5 13.5 L2 12 L10.5 10.5 Z"
          fill="#6366f1" stroke="#6366f1" stroke-width="0.5" stroke-linejoin="round"/></svg>`;
      document.body.appendChild(star);
      let spinTimer = null;
      document.addEventListener('mousemove', (e) => {
        star.style.left = e.clientX + 'px';
        star.style.top  = e.clientY + 'px';
        star.classList.add('spinning');
        clearTimeout(spinTimer);
        spinTimer = setTimeout(() => star.classList.remove('spinning'), 150);
      });
      document.addEventListener('mouseleave', () => star.style.opacity = '0');
      document.addEventListener('mouseenter', () => star.style.opacity = '1');
      let lastX = -999, lastY = -999;
      document.addEventListener('mousemove', (e) => {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        if (Math.sqrt(dx*dx + dy*dy) < 12) return;
        lastX = e.clientX; lastY = e.clientY;
        const isDark = root.getAttribute('data-theme') === 'dark';
        const colors = isDark ? darkColors : lightColors;
        const dot = document.createElement('div');
        dot.className = 'trail-particle';
        const size = Math.random() * 6 + 4;
        dot.style.cssText = `width:${size}px;height:${size}px;background:${colors[Math.floor(Math.random()*colors.length)]};left:${e.clientX}px;top:${e.clientY}px;opacity:${isDark?0.85:0.7}`;
        document.body.appendChild(dot);
        dot.addEventListener('animationend', () => dot.remove());
      });
    }
  </script>
  <script src="cursor-halo.js"></script>
</body>
</html>
```

- [ ] **Step 2: Verify the page renders correctly**

Open `downloads.html` in a browser. Verify:
- Dark/light theme toggle works
- Hamburger nav opens and links work
- "Downloads" title and "Apps built by Alwin" subtitle visible
- Calculator card displays with icon, name, description
- All 4 platform buttons show greyed out with "Coming Soon" tooltip on hover
- Mobile responsive: buttons stack vertically on small screens
- Star cursor and particle trail work

- [ ] **Step 3: Commit**

```bash
git add downloads.html
git commit -m "feat: add Downloads Zone page with Calculator app card"
```

---

### Task 2: Enable a download button (when a build is ready)

**Files:**
- Modify: `downloads.html`

This task documents how to activate a button when a build becomes available. No code to write now — this is a reference for future use.

- [ ] **Step 1: When a build is ready, update the button**

To activate a platform button (e.g., Android `.apk` is ready), find the relevant `<span class="platform-btn-wrap">` block in `downloads.html` and replace it with an `<a>` link. For example, to activate the Android button:

**Before (coming soon):**
```html
<span class="platform-btn-wrap">
  <span class="tooltip">Coming Soon</span>
  <span class="platform-btn coming-soon">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.523 15.341..."/></svg>
    Android
  </span>
</span>
```

**After (active download):**
```html
<a class="platform-btn" href="https://github.com/alwinthomas/calculator-app/releases/download/v1.0.0/calculator.apk" download>
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.523 15.341..."/></svg>
  Android
</a>
```

Key changes:
- `<span class="platform-btn-wrap">` wrapper removed
- `<span>` becomes `<a>` with `href` pointing to the GitHub Release asset URL
- `coming-soon` class removed
- `download` attribute added so browser downloads instead of navigating
- Tooltip span removed

- [ ] **Step 2: Commit the change**

```bash
git add downloads.html
git commit -m "feat: activate Android download link for Calculator v1.0.0"
```
