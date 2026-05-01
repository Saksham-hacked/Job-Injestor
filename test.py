import asyncio
from patchright.async_api import async_playwright

async def debug_one_page_and_dump():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Hit the search page
        print("Fetching search results...")
        await page.goto("https://www.ecommunity.com/careers/search?category=All&page=1", wait_until="networkidle")
        
        # Wait for the cards to actually exist in the browser DOM
        try:
            await page.wait_for_selector("article.job-teaser", timeout=10000)
        except Exception:
            print("Timeout: Job cards didn't load. Check if the URL changed.")
            await browser.close()
            return

        # 2. Get the first link using browser-side execution
        first_job_url = await page.evaluate('''() => {
            const link = document.querySelector('article.job-teaser .title a');
            return link ? link.href : null;
        }''')

        if not first_job_url:
            print("Could not find a job link on the page.")
            await browser.close()
            return

        print(f"Targeting: {first_job_url}")

        # 3. Go to the deep page and wait for content
        await page.goto(first_job_url, wait_until="networkidle")
        
        # Wait for common JD keywords to ensure the text is rendered
        await asyncio.sleep(2) 
        
        # 4. Dump the fully rendered HTML
        rendered_html = await page.content()
        
        with open("deep_page_dump.html", "w", encoding="utf-8") as f:
            f.write(rendered_html)
            
        print("✅ Success! Fully rendered HTML saved to 'deep_page_dump.html'.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_one_page_and_dump())