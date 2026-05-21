'use strict';
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE_URL = process.env.DEMO_URL || 'https://crzcheck.bacimo.net';
const OUTPUT_DIR = path.join(__dirname, '..', 'docs');
const OUTPUT_NAME = 'demo-video.webm';
const REHEARSAL = process.argv.includes('--rehearse');

// ─── Helpers ────────────────────────────────────────────────────────────────

async function injectCursor(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-cursor')) return;
    const cursor = document.createElement('div');
    cursor.id = 'demo-cursor';
    cursor.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/>
    </svg>`;
    cursor.style.cssText = `
      position: fixed; z-index: 999999; pointer-events: none;
      width: 24px; height: 24px;
      transition: left 0.1s, top 0.1s;
      filter: drop-shadow(1px 1px 2px rgba(0,0,0,0.3));
    `;
    cursor.style.left = '100px';
    cursor.style.top = '100px';
    document.body.appendChild(cursor);
    document.addEventListener('mousemove', (e) => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
    });
  });
}

async function injectSubtitleBar(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-subtitle')) return;
    const bar = document.createElement('div');
    bar.id = 'demo-subtitle';
    bar.style.cssText = `
      position: fixed; bottom: 0; left: 0; right: 0; z-index: 999998;
      text-align: center; padding: 12px 24px;
      background: rgba(0, 0, 0, 0.75);
      color: white; font-family: -apple-system, "Segoe UI", sans-serif;
      font-size: 16px; font-weight: 500; letter-spacing: 0.3px;
      transition: opacity 0.3s;
      pointer-events: none;
    `;
    bar.textContent = '';
    bar.style.opacity = '0';
    document.body.appendChild(bar);
  });
}

async function showSubtitle(page, text) {
  await page.evaluate((t) => {
    const bar = document.getElementById('demo-subtitle');
    if (!bar) return;
    if (t) {
      bar.textContent = t;
      bar.style.opacity = '1';
    } else {
      bar.style.opacity = '0';
    }
  }, text);
  if (text) await page.waitForTimeout(800);
}

async function moveAndClick(page, locator, label, opts = {}) {
  const { postClickDelay = 800, ...clickOpts } = opts;
  const el = typeof locator === 'string' ? page.locator(locator).first() : locator;
  const visible = await el.isVisible().catch(() => false);
  if (!visible) {
    console.error(`WARNING: moveAndClick skipped - "${label}" not visible`);
    return false;
  }
  try {
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const box = await el.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
      await page.waitForTimeout(400);
    }
    await el.click(clickOpts);
  } catch (e) {
    console.error(`WARNING: moveAndClick failed on "${label}": ${e.message}`);
    return false;
  }
  await page.waitForTimeout(postClickDelay);
  return true;
}

async function tryExpandSidebar(page) {
  // Streamlit sidebar toggle button
  const btn = page.locator('button[aria-label="Open sidebar"]').first();
  const visible = await btn.isVisible().catch(() => false);
  if (visible) {
    console.log('Expanding sidebar...');
    await btn.click();
    await page.waitForTimeout(1000);
  } else {
    console.log('Sidebar already open or no toggle found');
  }
}

async function typeSlowly(page, locator, text, label, charDelay = 35) {
  const el = typeof locator === 'string' ? page.locator(locator).first() : locator;
  const visible = await el.isVisible().catch(() => false);
  if (!visible) {
    console.error(`WARNING: typeSlowly skipped - "${label}" not visible`);
    return false;
  }
  await moveAndClick(page, el, label);
  await el.fill('');
  await el.pressSequentially(text, { delay: charDelay });
  await page.waitForTimeout(500);
  return true;
}

async function ensureVisible(page, locator, label) {
  const el = typeof locator === 'string' ? page.locator(locator).first() : locator;
  const visible = await el.isVisible().catch(() => false);
  if (!visible) {
    console.error(`REHEARSAL FAIL: "${label}" not found`);
    return false;
  }
  console.log(`REHEARSAL OK: "${label}"`);
  return true;
}

async function panElements(page, selector, maxCount = 6) {
  const elements = await page.locator(selector).all();
  for (let i = 0; i < Math.min(elements.length, maxCount); i++) {
    try {
      const box = await elements[i].boundingBox();
      if (box && box.y < 700 && box.y > 0) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 8 });
        await page.waitForTimeout(600);
      }
    } catch (e) {
      console.warn(`WARNING: panElements skipped element ${i}: ${e.message}`);
    }
  }
}

async function afterNavigate(page) {
  await page.waitForTimeout(3000); // Let Streamlit render fully
  await injectCursor(page);
  await injectSubtitleBar(page);
}

async function navigateTo(page, pageName) {
  const link = page.locator(`a:has-text("${pageName}")`).first();
  await moveAndClick(page, link, `${pageName} nav`, { postClickDelay: 4000 });
  await afterNavigate(page);
}

// ─── Main ───────────────────────────────────────────────────────────────────

(async () => {
  const browser = await chromium.launch({ headless: true });

  if (REHEARSAL) {
    console.log('=== REHEARSAL MODE ===');
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    const page = await context.newPage();

    await page.goto(BASE_URL);
    await afterNavigate(page);
    await tryExpandSidebar(page);

    const steps = [
      { label: 'Home nav', selector: 'a:has-text("Home")' },
      { label: 'Oznamy nav', selector: 'a:has-text("Oznamy")' },
      { label: 'Detail zmluvy nav', selector: 'a:has-text("Detail zmluvy")' },
      { label: 'Organizacie nav', selector: 'a:has-text("Organizacie")' },
      { label: 'Stav dat nav', selector: 'a:has-text("Stav dat")' },
      { label: 'Metodika nav', selector: 'a:has-text("Metodika")' },
    ];

    // Check home page elements
    const searchVisible = await page.locator('input[aria-label="Hľadať"]').first().isVisible().catch(() => false);
    console.log(`Search input visible: ${searchVisible}`);

    // Check Oznamy
    await navigateTo(page, 'Oznamy');
    await tryExpandSidebar(page);
    for (const step of [
      { label: 'Severity dropdown', selector: 'input[aria-label*="Závažnosť"]' },
      { label: 'CSV download', selector: 'button:has-text("Stiahnuť CSV")' },
    ]) {
      await ensureVisible(page, step.selector, step.label);
    }

    // Check Detail zmluvy
    await navigateTo(page, 'Detail zmluvy');
    await ensureVisible(page, 'input[aria-label="Zadajte ID zmluvy:"]', 'Contract ID input');

    await browser.close();
    console.log('REHEARSAL COMPLETE');
    return;
  }

  // ─── RECORD ──────────────────────────────────────────────────────────────
  console.log('=== RECORDING MODE ===');
  const context = await browser.newContext({
    recordVideo: { dir: OUTPUT_DIR, size: { width: 1280, height: 720 } },
    viewport: { width: 1280, height: 720 }
  });
  const page = await context.newPage();

  try {
    // ── Step 1: Home page ──
    await page.goto(BASE_URL);
    await afterNavigate(page);
    await tryExpandSidebar(page);

    await showSubtitle(page, 'CRZ Risk & Quality Monitor — Prehľad verejných zákaziek');
    await page.waitForTimeout(3000);

    // Pan across home page metrics
    await panElements(page, '[data-testid="stMetricValue"]', 6);
    await page.waitForTimeout(1500);

    // Scroll down to show contract table
    await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
    await page.waitForTimeout(2000);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);

    // ── Step 2: Oznamy ──
    await showSubtitle(page, 'Oznamy — Zmluvy s rizikovými vlajkami');
    await navigateTo(page, 'Oznamy');
    await tryExpandSidebar(page);
    await page.waitForTimeout(2000);

    // Scroll through flagged contracts
    await page.evaluate(() => window.scrollTo({ top: 300, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);

    // Show severity filter
    await showSubtitle(page, 'Filtrovanie podľa závažnosti a typu');
    await moveAndClick(page, 'input[aria-label*="Závažnosť"]', 'Severity dropdown');
    await page.waitForTimeout(1200);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(800);

    // Show CSV export
    await showSubtitle(page, 'Export dát do CSV');
    await moveAndClick(page, 'button:has-text("Stiahnuť CSV")', 'CSV download button', { postClickDelay: 1500 });

    // ── Step 3: Contract detail ──
    await showSubtitle(page, 'Detail zmluvy — Rizikové príznaky konkrétnej zmluvy');
    await navigateTo(page, 'Detail zmluvy');

    const idInput = 'input[aria-label="Zadajte ID zmluvy:"]';
    await moveAndClick(page, idInput, 'Contract ID input');
    await typeSlowly(page, idInput, '12352940', 'Contract ID');
    await page.waitForTimeout(3000);

    // Scroll to see results
    await page.evaluate(() => window.scrollTo({ top: 300, behavior: 'smooth' }));
    await page.waitForTimeout(2000);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);

    // ── Step 4: Organizations ──
    await showSubtitle(page, 'Organizácie — Objednávatelia podľa objemu');
    await navigateTo(page, 'Organizacie');
    await page.waitForTimeout(2000);

    // Pan through org list
    await panElements(page, 'a:has-text("🔗")', 5);
    await page.waitForTimeout(1000);
    await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);

    // ── Step 5: Metodika ──
    await showSubtitle(page, 'Metodika — Ako hodnotíme riziká');
    await navigateTo(page, 'Metodika');
    await page.waitForTimeout(2000);

    // Scroll through methodology
    await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo({ top: 800, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);

    // ── Step 6: Data status ──
    await showSubtitle(page, 'Stav dát — Aktuálnosť a kvalita dát');
    await navigateTo(page, 'Stav dat');
    await page.waitForTimeout(2000);

    await panElements(page, '[data-testid="stMetricValue"]', 6);
    await page.waitForTimeout(1500);

    // Scroll for more metrics
    await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
    await page.waitForTimeout(1500);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await page.waitForTimeout(1000);

    // ── Final: Back to Home ──
    await showSubtitle(page, 'CRZ Risk & Quality Monitor — crzcheck.bacimo.net');
    await navigateTo(page, 'Home');
    await page.waitForTimeout(3000);
    await showSubtitle(page, '');
    await page.waitForTimeout(2000);

    console.log('Recording complete!');
  } catch (err) {
    console.error('DEMO ERROR:', err.message);
    console.error(err.stack);
  } finally {
    await context.close();
    const video = page.video();
    if (video) {
      const src = await video.path();
      const dest = path.join(OUTPUT_DIR, OUTPUT_NAME);
      try {
        fs.copyFileSync(src, dest);
        const size = fs.statSync(dest).size;
        console.log(`Video saved: ${dest} (${(size / 1024 / 1024).toFixed(1)} MB)`);
      } catch (e) {
        console.error('ERROR copying video:', e.message);
      }
    }
    await browser.close();
  }
})();
