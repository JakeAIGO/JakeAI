# GRIDWORKS — Official Website Repository (gridworkstheshow.com)

**Release:** Master v34 (Jim Website Build Instructions — Clean Single-File Root)  
**WGAW Registration:** #2354100 (2026–2031)  
**Domain:** `gridworkstheshow.com`  
**Creator & Host:** Jason Horn (`jason@solutionser.com` | `(540) 529-1988` | Roanoke, VA)

---

## 1. Repository Structure (Flat Root / Zero Subfolders)

This repository is strictly configured with **zero subfolders** to ensure instant compatibility with GitHub Pages, Netlify, and direct git commits:

```text
├── index.html       # 100% Self-Contained Master Production File (HTML + CSS + JS)
└── README.md        # Repository Documentation & Sizzle Reel Configuration
```

- **Zero Asset Subfolders:** All architectural styling, typography, interactive modals, and screening player scripts are embedded directly inside `index.html`.
- **Zero Broken Paths:** Can be deployed to the root of any repository, branch, or web server without path resolution errors.

---

## 2. How to Swap the Sizzle Reel (One-Variable Change)

To update the screening reel across the entire website, open `index.html`, scroll to line ~770 (inside the `<script>` tag), and update the `youtubeId` in `GRIDWORKS_CONFIG`:

```javascript
const GRIDWORKS_CONFIG = {
  sizzle: {
    title: "GRIDWORKS — Official Buyer Sizzle Reel",
    youtubeId: "S06lt58Kp_8", // <-- Replace this YouTube ID
    duration: "90 Seconds",
    format: "4K HDR Factual Preview"
  },
  ...
};
```

Saving and committing `index.html` immediately updates the screening player and modal across the entire website.

---

## 3. Deployment Instructions

### GitHub Pages (Custom Domain `gridworkstheshow.com`)
1. Commit and push `index.html` and `README.md` directly to the `main` branch of your repository (`gridworkstheshow`).
2. In GitHub repository settings: **Settings -> Pages**.
3. Under **Build and deployment**, set Source to **Deploy from a branch**, Branch to `main`, and folder to `/ (root)`.
4. Under **Custom domain**, enter `gridworkstheshow.com` and save.

### Netlify
- Drag and drop `index.html` or the unzipped folder directly into the Netlify manual deploy drop zone.
