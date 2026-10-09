const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const pages = ['/home', '/chat', '/search', '/blood', '/meds', '/calculators', '/about-us'];
for (const path of pages) {
  test(`WCAG smoke ${path}`, async ({ page, baseURL }) => {
    await page.context().addCookies([{ name: 'lang', value: 'ar', url: baseURL }]);
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    const serious = results.violations.filter(v => ['critical','serious'].includes(v.impact));
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });
}
