import asyncio
import json
import re
from bs4 import BeautifulSoup
from patchright.async_api import async_playwright

OUTPUT_FILE = "methodist_jobs.json"
MAX_CONCURRENT_REQUESTS = 5
BASE_URL = "https://careers-methodisthospitals.icims.com"
# iCIMS uses 'pr=' for pagination (0=Page 1, 1=Page 2, etc.)
SEARCH_URL = f"{BASE_URL}/jobs/search?ss=1&searchRelation=keyword_all&pr="

async def fetch_job_details(context, job: dict, semaphore: asyncio.Semaphore) -> dict:
    """Fetches full description and Req ID from the job's individual page."""
    async with semaphore:
        url = job.get("Job URL")
        if not url: return job
        
        page = await context.new_page()
        try:
            # Block heavy assets to focus on text content
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2}", lambda route: route.abort())
            
            # Use 'domcontentloaded' for speed
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # iCIMS detail pages are also often inside the iframe
            frame = page.frame(name="icims_content_iframe") or page.main_frame
            await frame.wait_for_selector(".iCIMS_JobContent", timeout=10000)
            
            content = await frame.content()
            soup = BeautifulSoup(content, "lxml")
            
            # Extract main description text
            jd_body = soup.select_one(".iCIMS_JobDetail")
            if jd_body:
                job["Full Description"] = jd_body.get_text(separator="\n", strip=True)
            
            # Extract Req ID if available
            req_id_elem = soup.find(string=re.compile(r"ID\s*\d+"))
            if req_id_elem:
                match = re.search(r"(\d+)", str(req_id_elem))
                if match: job["Req ID"] = match.group(1)

        except Exception as e:
            print(f"  [!] Detail Error at {url}: {e}")
        finally:
            await page.close()
        return job

async def scrape_methodist():
    all_jobs = []
    current_page = 0 
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        # print("--- PHASE 1: Indexing iCIMS Portal ---")
        # page = await context.new_page()
        
        # while True:
        #     target_url = f"{SEARCH_URL}{current_page}"
        #     print(f"Fetching Page {current_page + 1}...")
            
        #     await page.goto(target_url, wait_until="networkidle")
            
        #     # Access the specific iframe identified in image_e3d753.jpg
        #     print("Available frames:", [f.name for f in page.frames])
        #     frame = page.frame(name="icims_content_iframe")
        #     if not frame:
        #         print("Could not locate iCIMS iframe. Ending search.")
        #         break

        #     # Wait for the specific job table container to load
        #     try:
        #         await frame.wait_for_selector(".iCIMS_JobsTable", timeout=15000)
        #     except:
        #         print("No more jobs found or page failed to render.")
        #         break

        #     html = await frame.content()
        #     soup = BeautifulSoup(html, "lxml")
        #     job_rows = soup.select(".iCIMS_JobsTable .row")
            
        #     if not job_rows:
        #         break

        #     for row in job_rows:
        #         link_tag = row.select_one("a.iCIMS_Anchor")
        #         if not link_tag: continue
                
        #         # Standard iCIMS metadata extraction
        #         job_data = {
        #             "Title": link_tag.get_text(strip=True),
        #             "Job URL": link_tag['href'],
        #             "Location": row.select_one("span[title*='Location']").parent.get_text(strip=True) 
        #                         if row.select_one("span[title*='Location']") else "N/A"
        #         }
        #         all_jobs.append(job_data)

        #     # Check for the presence of a 'Next' button to continue pagination
        #     next_btn = soup.select_one("a:has(.glyphicon-chevron-right)")
        #     if not next_btn:
        #         break
                
        #     current_page += 1
        #     await asyncio.sleep(1) # Polite delay
        print("--- PHASE 1: Indexing iCIMS Portal ---")
        page = await context.new_page()
        
        target_url = f"{SEARCH_URL}{current_page}"
        print(f"Navigating to: {target_url}")
        
        # 1. Navigate and wait for the network to settle
        await page.goto(target_url, wait_until="networkidle")

        # 2. Find the frame by scanning all frames for the iCIMS table
        # This bypasses the need for the "#icims_content_iframe" ID
        print("Scanning all frames for job data...")
        target_frame = None
        for frame in page.frames:
            try:
                # Based on image_e307e4.jpg, we look for the specific job table class
                if await frame.locator("ul.iCIMS_JobsTable").count() > 0:
                    target_frame = frame
                    break
            except:
                continue

        if not target_frame:
            print("Could not find iCIMS table in any frame. Capturing debug info...")
            await page.screenshot(path="no_frame_found.png")
            # Dump HTML to see if the site is serving a 'Bot Detected' page
            content = await page.content()
            with open("source_dump.html", "w", encoding="utf-8") as f:
                f.write(content)
            return

        print(f"Target frame located: {target_frame.url[:60]}...")

        # 3. Wait for the list items to be visible inside the found frame
        job_cards_locator = target_frame.locator("li.iCIMS_JobCardItem")
        try:
            await job_cards_locator.first.wait_for(state="visible", timeout=10000)
        except:
            print("Frame found, but job cards never became visible.")
            return

        # 4. Extract data using selectors confirmed in image_e307e4.jpg
        count = await job_cards_locator.count()
        print(f"Found {count} jobs on this page.")

        for i in range(count):
            card = job_cards_locator.nth(i)
            
            # The title and URL are inside the 'a.iCIMS_Anchor'
            title_link = card.locator("a.iCIMS_Anchor")
            
            # Location is in the .header.right div
            location_text = await card.locator(".header.right span:not(.sr-only)").first.inner_text()
            
            all_jobs.append({
                "Title": await title_link.locator("h3").inner_text(),
                "Job URL": await title_link.get_attribute("href"),
                "Location": location_text.strip() if location_text else "N/A"
            })

        # 5. Check for 'Next' button to break/continue the while loop
        # iCIMS 'Next' usually has the chevron-right icon
        next_btn = target_frame.locator("a:has(.glyphicon-chevron-right)")
        if await next_btn.count() == 0:
            print("Reached the last page.")
            # Set loop control variable to break here

        print(f"\n--- PHASE 2: Fetching Descriptions for {len(all_jobs)} Jobs ---")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        tasks = [fetch_job_details(context, job, semaphore) for job in all_jobs]
        results = await asyncio.gather(*tasks)

        await browser.close()

    # Save all combined results
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\nScraping complete. {len(results)} jobs saved to {OUTPUT_FILE}.")

if __name__ == "__main__":
    asyncio.run(scrape_methodist())