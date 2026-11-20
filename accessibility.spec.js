// WCAG 2.2 AA smoke test with axe-core, every public page in Arabic and English.
// Mirrors tools/accessibility_audit.py (which also measures touch-target sizes): keep the lists in sync.
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const pages = ['', 'chat', 'consent', 'search', 'blood', 'meds', 'calculators', 'emergency', 'firstaid', 'tips', 'relax',
  'health-library', 'health-trends', 'about', 'how-we-work', 'privacy', 'terms', 'contact', 'login', 'register', 'live-demo'];
for (const lang of ['ar', 'en']) {
  for (const slug of pages) {
    test(`WCAG 2.2 AA /${lang}/${slug}`, async ({ page }) => {
      await page.goto(`/${lang}/${slug}`, { waitUntil: 'networkidle' });
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
      const serious = results.violations.filter(v => ['critical','serious'].includes(v.impact));
      expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
    });
  }
}
