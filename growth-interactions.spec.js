const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ context, baseURL }) => {
  await context.addCookies([{ name: 'lang', value: 'ar', url: baseURL }]);
});

test('assistant consent returns to an existing, open assistant', async ({ page }) => {
  await page.goto('/home?assistant=general');
  await page.locator('#asstInput').fill('ما هو الصداع؟');
  await page.locator('#asstSendBtn').click();
  await expect(page).toHaveURL(/\/consent/);
  await page.locator('#serviceConsent').check();
  await page.locator('#consentForm button[type=submit]').click();
  await expect(page).toHaveURL(/\/home\?assistant=general/);
  await expect(page.locator('#asstPanel')).toHaveClass(/open/);
});

test('home explanation opens and closes by clicking', async ({ page }) => {
  await page.goto('/home');
  await page.locator('#heroDemoOpen').click();
  await expect(page.locator('#heroDemoClose')).toBeVisible();
  await page.locator('#heroDemoClose').click();
  await expect(page.locator('#heroDemoClose')).toBeHidden();
});

test('microphone denial gives feedback and preserves typed symptoms', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'SpeechRecognition', { value: undefined });
    Object.defineProperty(window, 'webkitSpeechRecognition', { value: undefined });
    Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
      value: () => Promise.reject(new DOMException('Denied', 'NotAllowedError')),
    });
  });
  await page.goto('/chat');
  await page.locator('#serviceConsent').check();
  await page.locator('#consentForm button[type=submit]').click();
  await page.locator('#textInp').fill('24');
  await page.locator('#chatInput button').click();
  await page.getByRole('button', { name: '👩 أنثى', exact: true }).click();
  await page.locator('#smartSymptomText').fill('صداع');
  await page.locator('#smartTextMicBtn').click();
  await expect(page.locator('#chatBody')).toContainText('تعذّر الإدخال الصوتي');
  await expect(page.locator('#smartSymptomText')).toHaveValue('صداع');
});
