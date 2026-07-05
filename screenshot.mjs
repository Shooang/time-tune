import { chromium } from 'playwright';

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2
  });
  const page = await context.newPage();
  
  console.log('Navigating to http://localhost:5193/...');
  await page.goto('http://localhost:5193/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  
  console.log('Waiting 4 seconds for page to load and intro...');
  await page.waitForTimeout(4000);
  
  try {
    await page.mouse.click(720, 450);
    console.log('Clicked center to start...');
    await page.waitForTimeout(3000);
  } catch (e) {
    console.log('Click error:', e.message);
  }
  
  console.log('Taking screenshot...');
  await page.screenshot({ path: '/tmp/radio_preview.png', fullPage: true });
  
  console.log('Screenshot saved to /tmp/radio_preview.png');
  await browser.close();
  console.log('Done!');
})();
