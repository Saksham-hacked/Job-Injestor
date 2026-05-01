# import asyncio
# import json
# from bs4 import BeautifulSoup
# from patchright.async_api import async_playwright

# # Updated output file name
# OUTPUT_FILE = "hhccorp.json"

# async def scrape_all_hhcorp_jobs():
#     all_jobs = []
#     startrow = 0
#     batch_size = 25  # Ensure this matches the amount of jobs returned per page
    
#     async with async_playwright() as p:
#         # Launch headless browser for a clean network context
#         browser = await p.chromium.launch(headless=True)
#         context = await browser.new_context(
#             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
#         )

#         previous_html = ""
        
#         while True:
#             # Clean API URL: No distance/keyword filters, fetching all jobs
#             api_url = f"https://careers.hhcorp.org/tile-search-results/?q=&sortColumn=referencedate&sortDirection=desc&startrow={startrow}"
            
#             print(f"Fetching jobs from offset {startrow}...")
            
#             response = await context.request.get(api_url)
            
#             if not response.ok:
#                 print(f"Server returned status {response.status}. Stopping.")
#                 break
                
#             html_content = await response.text()
            
#             # THE FIX: Check if the server is just spitting back the exact same HTML as the last request
#             if html_content == previous_html:
#                 print("Server is repeating the same page. End of database reached.")
#                 break
#             previous_html = html_content

#             soup = BeautifulSoup(html_content, "lxml")
#             job_rows = soup.select(".job-tile") 
            
#             if not job_rows:
#                 print("No more job tiles found in HTML. Pagination complete.")
#                 break
                
#             for row in job_rows:
#                 title_tag = row.select_one('.jobTitle a')
#                 title = title_tag.get_text(strip=True) if title_tag else ""
                
#                 all_jobs.append({
#                     "title": title,
#                     "raw_text": row.get_text(separator=" | ", strip=True) 
#                 })
                
#             # THE FIX (Backup): If a page returns fewer than the batch size, it's the last page.
#             if len(job_rows) < batch_size:
#                 print(f"Reached final page ({len(job_rows)} jobs). Pagination complete.")
#                 break

#             startrow += batch_size
#             await asyncio.sleep(1)
#         await browser.close()
        
#     # Save the full dataset to hhccorp.json
#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(all_jobs, f, indent=2, ensure_ascii=False)
        
#     print(f"\n✅ Successfully scraped {len(all_jobs)} total jobs to {OUTPUT_FILE}.")

# if __name__ == "__main__":
#     asyncio.run(scrape_all_hhcorp_jobs())



import asyncio
import json
import re
from bs4 import BeautifulSoup
from patchright.async_api import async_playwright

OUTPUT_FILE = "hhccorp.json"
MAX_CONCURRENT_REQUESTS = 8  # Adjust if the server starts throwing 429 Too Many Requests

def parse_job_text(raw_string: str) -> dict:
    """Cleans the pipe-separated string into a deduplicated dictionary."""
    parts = [p.strip() for p in raw_string.split('|') if p.strip()]
    parsed_data = {}
    
    for i in range(0, len(parts) - 1, 2):
        key = parts[i]
        value = parts[i+1]
        
        # Ignore accessibility junk text
        if "Select with space bar" in key or "Select with space bar" in value:
            continue
            
        # Add key if not already present (removes repetition)
        if key not in parsed_data:
            parsed_data[key] = value
            
    return parsed_data


async def fetch_job_details(context, job: dict, semaphore: asyncio.Semaphore) -> dict:
    """Fetches deep details, extracting header metadata and embedded text fields."""
    async with semaphore:
        job_url = job.get("Job URL")
        
        job["Req ID"] = ""
        job["Date Posted"] = ""
        job["Company"] = ""
        job["Full Description"] = ""

        if not job_url:
            return job

        try:
            response = await context.request.get(job_url)
            if not response.ok:
                print(f"  [!] Failed to load {job_url} - Status: {response.status}")
                return job
                
            html_content = await response.text()
            soup = BeautifulSoup(html_content, "lxml")

            # 1. Extract Full Description
            desc_elem = soup.select_one(".jobdescription")
            if desc_elem:
                job["Full Description"] = desc_elem.get_text(separator="\n\n", strip=True)

            # 2. Extract Req ID from the description body (HHC specific)
            req_match = re.search(r"Req ID:\s*(\d+)", job["Full Description"], re.IGNORECASE)
            if req_match:
                job["Req ID"] = req_match.group(1)

            # 3. Extract Header Metadata (Date, Company)
            # SuccessFactors puts these in spans or divs near the top. 
            # We iterate through all span and b tags to catch them safely.
           # 3. Extract Header Metadata (Date, Organization) based on exact DOM structure
            
           # 3. Extract Header Metadata (Date, Company) using explicit CSS IDs
            
            # --- Date Posted ---
            date_p = soup.select_one('#job-date, .jobDate')
            if date_p:
                raw_date = date_p.get_text(strip=True)
                job["Date Posted"] = re.sub(r"Date:\s*", "", raw_date, flags=re.IGNORECASE).strip()

            # --- Company / Organization ---
            org_p = soup.select_one('#job-company, .jobCompany')
            if org_p:
                raw_org = org_p.get_text(strip=True)
                job["Company"] = re.sub(r"(Organization|Company):\s*", "", raw_org, flags=re.IGNORECASE).strip()

        except Exception as e:
            print(f"  [!] Error parsing details for {job_url}: {e}")

        return job
async def scrape_all_hhcorp_jobs():
    all_jobs = []
    startrow = 0
    batch_size = 25
    previous_html = ""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        print("--- PHASE 1: Fetching Job Listings ---")
        while True:
            api_url = f"https://careers.hhcorp.org/tile-search-results/?q=&sortColumn=referencedate&sortDirection=desc&startrow={startrow}"
            print(f"Fetching offset {startrow}...")
            
            response = await context.request.get(api_url)
            if not response.ok:
                print(f"Server returned status {response.status}. Stopping pagination.")
                break
                
            html_content = await response.text()
            
            if html_content == previous_html:
                print("Server repeated the same HTML. End of database reached.")
                break
            previous_html = html_content

            soup = BeautifulSoup(html_content, "lxml")
            job_rows = soup.select(".job-tile") 
            
            if not job_rows:
                break
                
            for row in job_rows:
                raw_text = row.get_text(separator="|", strip=True) 
                clean_data = parse_job_text(raw_text)
                
                link_tag = row.find('a')
                clean_data["Job URL"] = "https://careers.hhcorp.org" + link_tag['href'] if link_tag and link_tag.has_attr('href') else ""
                
                all_jobs.append(clean_data)
                
            if len(job_rows) < batch_size:
                break

            startrow += batch_size
            await asyncio.sleep(0.5) 

        print(f"\n--- PHASE 2: Fetching Deep Details Concurrently ({MAX_CONCURRENT_REQUESTS} at a time) ---")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        
        # Create a list of concurrent tasks
        tasks = [
            fetch_job_details(context, job, semaphore)
            for job in all_jobs
        ]
        
        # Execute them and wait for all to finish
        all_jobs = await asyncio.gather(*tasks)

        await browser.close()
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
        
    print(f"\nExecution Complete. Saved {len(all_jobs)} jobs to {OUTPUT_FILE}.")

if __name__ == "__main__":
    asyncio.run(scrape_all_hhcorp_jobs())