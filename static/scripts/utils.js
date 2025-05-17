const puppeteer = require('puppeteer');

(async () => {
    // Launch browser
    const browser = await puppeteer.launch({
        headless: 'new', 
        defaultViewport: { width: 1000, height: 2300 } // adjust as needed
    });
    const page = await browser.newPage();

    // Go to your local or deployed page
    await page.goto('file://' + require('path').resolve('docs/current_chart/index.html'));
    await page.evaluate(() => {
        document.querySelector('#rightToolbar')?.remove();
      });

   
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Select the  node
    const chart = await page.$('.container');
    if (chart) {
        await chart.screenshot({ path: 'chart.png' });
        console.log('Screenshot saved as chart.png');
    } else {
        // fallback: screenshot full page
        await page.screenshot({ path: 'fullpage.png', fullPage: true });
        console.log('Chart not found, saved full page as fullpage.png');
    }

    await browser.close();
})();
