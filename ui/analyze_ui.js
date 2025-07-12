const puppeteer = require('puppeteer');

async function analyzeUI() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    
    // Go to the dashboard
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle2', timeout: 10000 });
    
    // Take screenshot
    await page.screenshot({ path: 'current_ui_screenshot.png', fullPage: true });
    
    // Get page content
    const pageContent = await page.content();
    console.log('=== PAGE STRUCTURE ===');
    
    // Check for podcast cards
    const podcastCards = await page.$$eval('.podcast-card', cards => cards.length);
    console.log(`Number of podcast cards found: ${podcastCards}`);
    
    // Get any error messages
    const errors = await page.$$eval('.error, .error-message', els => els.map(el => el.textContent));
    if (errors.length > 0) {
      console.log('Errors found:', errors);
    }
    
    // Check for loading states
    const loadingElements = await page.$$eval('.loading, [class*="loading"]', els => els.length);
    console.log(`Loading elements: ${loadingElements}`);
    
    // Get all visible text content
    const textContent = await page.evaluate(() => {
      return document.body.innerText;
    });
    console.log('\n=== VISIBLE TEXT CONTENT ===');
    console.log(textContent);
    
  } catch (error) {
    console.error('Error analyzing UI:', error);
  } finally {
    await browser.close();
  }
}

analyzeUI();