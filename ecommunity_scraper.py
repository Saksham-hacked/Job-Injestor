import asyncio
import json
import re
from bs4 import BeautifulSoup
from patchright.async_api import async_playwright

OUTPUT_FILE = "ecommunity.json"
MAX_CONCURRENT_REQUESTS = 8
BASE_URL = "https://www.ecommunity.com"
# The UI shows page=1, page=2 etc.
SEARCH_URL = f"{BASE_URL}/careers/search?category=All&keyword=&page="

async def fetch_job_details(context, job: dict, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        job_url = job.get("Job URL")
        if not job_url:
            return job

        page = await context.new_page()
        try:
            # 1. Brutal resource blocking to stop the timeout bleed
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2,google-analytics.com,doubleclick.net}", lambda route: route.abort())
            
            # 2. Faster wait state
            await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
            
            # 3. Targeted wait for the actual content container
            # This is much faster than waiting for the entire network to be idle
            try:
                await page.wait_for_selector(".right.job-content", timeout=5000)
            except:
                pass # Proceed anyway to try and scrape what's there

            content = await page.content()
            soup = BeautifulSoup(content, "lxml")

            # Description extraction with the confirmed dot selector
            desc_elem = soup.select_one(".right.job-content")
            if desc_elem:
                job["Full Description"] = desc_elem.get_text(separator="\n", strip=True)

            # Sidebar extraction
            sidebar = soup.select_one(".left.job-content")
            if sidebar:
                def get_field(class_name):
                    elem = sidebar.select_one(f".field--name-field-job-{class_name} .field__item, .field--name-field-{class_name} .field__item")
                    return elem.get_text(strip=True) if elem else None
                job["Category"] = get_field("category") or job.get("Category")
                job["Hours"] = get_field("hours") or job.get("Hours")

            # Req ID from URL suffix
            url_req = re.search(r"-(\d+)$", job_url)
            if url_req:
                job["Req ID"] = url_req.group(1)

        except Exception as e:
            print(f"  [!] Error rendering {job_url}: {e}")
        finally:
            await page.close()

        return job

async def scrape_ecommunity():
    all_jobs = []
    current_page = 1 
    previous_html = ""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        print("--- PHASE 1: Indexing Job Cards ---")
        while current_page==1:
            target_url = f"{SEARCH_URL}{current_page}"
            print(f"Fetching Page {current_page}...")
            
            # Navigate to page
            page = await context.new_page()
            # Intercept images/css to save bandwidth during indexing
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2}", lambda route: route.abort())
            await page.goto(target_url, wait_until="domcontentloaded")
            
            html_content = await page.content()
            
            # Loop breaker: check if content is identical to last page
            if html_content == previous_html:
                await page.close()
                break
            previous_html = html_content

            soup = BeautifulSoup(html_content, "lxml")
            cards = soup.select("article.job-teaser")
            
            if not cards:
                print("No more jobs found.")
                await page.close()
                break
                
            for card in cards:
                title_tag = card.select_one(".title a")
                
                # Extracting fields based on provided Drupal classes
                job_data = {
                    "Title": title_tag.get_text(strip=True) if title_tag else "N/A",
                    "Job URL": BASE_URL + title_tag['href'] if title_tag else "",
                    "Department": card.select_one(".field--name-field-job-department").get_text(strip=True) if card.select_one(".field--name-field-job-department") else "N/A",
                    "Schedule": card.select_one(".field--name-field-job-schedule").get_text(strip=True) if card.select_one(".field--name-field-job-schedule") else "N/A",
                    "Shift": card.select_one(".field--name-field-job-shift").get_text(strip=True) if card.select_one(".field--name-field-job-shift") else "N/A",
                    "Facility": card.select_one(".field--name-field-job-location-name").get_text(strip=True) if card.select_one(".field--name-field-job-location-name") else "N/A",
                    "Location": card.select_one(".field--name-field-address").get_text(strip=True) if card.select_one(".field--name-field-address") else "N/A",
                }
                all_jobs.append(job_data)
            
            await page.close()
            
            # Check for 'Next' button presence to continue
            if not soup.select_one("li.pager__item--next"):
                break

            current_page += 1
            await asyncio.sleep(0.5)

        print(f"\n--- PHASE 2: Deep Fetching {len(all_jobs)} JDs ---")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        tasks = [fetch_job_details(context, job, semaphore) for job in all_jobs]
        all_jobs = await asyncio.gather(*tasks)

        await browser.close()
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
        
    print(f"\nScraping complete. {len(all_jobs)} jobs saved to {OUTPUT_FILE}.")






if __name__ == "__main__":
    asyncio.run(scrape_ecommunity())


# import asyncio
# import json
# import re
# from bs4 import BeautifulSoup
# from patchright.async_api import async_playwright

# OUTPUT_FILE = "ecommunity.json"
# MAX_CONCURRENT_REQUESTS = 8
# BASE_URL = "https://www.ecommunity.com"
# SEARCH_URL = f"{BASE_URL}/careers/search?category=All&page="

# async def fetch_job_details(context, job: dict, semaphore: asyncio.Semaphore) -> dict:
#     async with semaphore:
#         job_url = job.get("Job URL")
#         if not job_url: return job
#         try:
#             # Phase 2: Direct request for speed
#             response = await context.request.get(job_url)
#             if not response.ok: return job
                
#             html_content = await response.text()
#             soup = BeautifulSoup(html_content, "lxml")

#             # Drupal common JD containers
#             desc_elem = soup.select_one(".node__content, .job-description, .field--name-body")
#             if desc_elem:
#                 job["Full Description"] = desc_elem.get_text(separator="\n\n", strip=True)
            
#             # Regex for Req ID
#             req_match = re.search(r"Req ID:\s*(\d+)", job.get("Full Description", ""), re.IGNORECASE)
#             if req_match:
#                 job["Req ID"] = req_match.group(1)
#         except Exception:
#             pass
#         return job

# async def scrape_ecommunity():
#     all_jobs = []
#     current_page = 0 # eCommunity might use 0-based or 1-based indexing; let's start at 0
    
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         context = await browser.new_context(user_agent="Mozilla/5.0 ...")

#         print("--- PHASE 1: Indexing ---")
#         page = await context.new_page()
        
#         while True:
#             target_url = f"{SEARCH_URL}{current_page}"
#             print(f"Checking Page {current_page}...")
            
#             try:
#                 await page.goto(target_url, wait_until="networkidle")
#                 # THE FIX: Wait for the specific job card to render
#                 await page.wait_for_selector("article.job-teaser", timeout=10000)
#             except Exception:
#                 print("No more job cards found or timeout reached. Ending Phase 1.")
#                 break

#             soup = BeautifulSoup(await page.content(), "lxml")
#             cards = soup.select("article.job-teaser")
            
#             for card in cards:
#                 title_tag = card.select_one(".title a")
#                 if not title_tag: continue
                
#                 all_jobs.append({
#                     "Title": title_tag.get_text(strip=True),
#                     "Job URL": BASE_URL + title_tag['href'],
#                     "Department": card.select_one(".field--name-field-job-department").get_text(strip=True) if card.select_one(".field--name-field-job-department") else "N/A",
#                     "Facility": card.select_one(".field--name-field-job-location-name").get_text(strip=True) if card.select_one(".field--name-field-job-location-name") else "N/A",
#                 })

#             if not soup.select_one("li.pager__item--next"):
#                 break
#             current_page += 1

#         print(f"Found {len(all_jobs)} jobs. Moving to Phase 2...")
#         semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
#         tasks = [fetch_job_details(context, job, semaphore) for job in all_jobs]
#         results = await asyncio.gather(*tasks)

#         with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#             json.dump(results, f, indent=2)
        
#         await browser.close()

# if __name__ == "__main__":
#     asyncio.run(scrape_ecommunity())


