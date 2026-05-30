# import asyncio
# import logging
# import json
# import random
# from bs4 import BeautifulSoup
# from camoufox.async_api import AsyncCamoufox
# from playwright_captcha import CaptchaType, ClickSolver, FrameworkType

# logging.basicConfig(
#     level='INFO',
#     format='[%(asctime)s] %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )

# OUTPUT_FILE = "searchpeoplefree_results.json"
# HEADLESS = False  # Keep false to watch the auto-solver work

# PEOPLE_TO_SEARCH = [
#     # Testing a highly generic name to guarantee results
#     {"first": "john", "last": "smith", "state": "ca", "city": "san-diego"}
# ]

# def build_search_url(person: dict) -> str:
#     base = f"https://www.searchpeoplefree.com/find/{person['first'].lower()}-{person['last'].lower()}"
#     if person.get("state"):
#         base += f"/{person['state'].lower()}"
#         if person.get("city"):
#             base += f"/{person['city'].lower().replace(' ', '-')}"
#     return base

# async def wait_and_solve_captcha(page, solver: ClickSolver) -> bool:
#     """Smart waiter: Looks for either the results or a CAPTCHA frame."""
#     logging.info("Checking page state (Results vs CAPTCHA)...")
    
#     # We poll the page for 15 seconds to see what renders
#     for _ in range(15):
#         # 1. Did we bypass entirely? Check for results.
#         if await page.query_selector("a[href*='/find/']"):
#             return False # Results are here, no captcha!

#         # 2. Check for Cloudflare / DataDome indicators
#         captcha_indicators = [
#             "iframe[src*='cloudflare']", 
#             "iframe[src*='datadome']", 
#             "iframe[src*='geo.captcha-delivery.com']",
#             "#challenge-stage",
#             ".cf-turnstile",
#             "#cf-please-wait"
#         ]
        
#         for sel in captcha_indicators:
#             if await page.query_selector(sel):
#                 logging.warning(f"⚠️ CAPTCHA detected via '{sel}'. Engaging Auto-Solver...")
#                 try:
#                     await solver.solve_captcha(
#                         captcha_container=page,
#                         captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
#                         # Tell the solver to expect link tags once the captcha is beaten
#                         expected_content_selector="a[href*='/find/']" 
#                     )
#                     await asyncio.sleep(3)
#                     logging.info("✅ Auto-solver finished successfully.")
#                     return True
#                 except Exception as e:
#                     logging.error(f"❌ Auto-Solver failed: {e}")
#                     if not HEADLESS:
#                         logging.info("⏳ Please click the CAPTCHA manually. Waiting 60 seconds...")
#                         try:
#                             await page.wait_for_selector("a[href*='/find/']", timeout=60000)
#                             logging.info("✅ Manual solve detected!")
#                             return True
#                         except Exception as manual_err:
#                             logging.error("Manual solve timed out.")
#                     return True 
        
#         await asyncio.sleep(1) # Wait 1 second and check the DOM again
        
#     return False

# async def scrape_person(browser, person: dict):
#     target_url = build_search_url(person)
#     page = await browser.new_page()
#     person["results"] = []
    
#     async with ClickSolver(framework=FrameworkType.PLAYWRIGHT, page=page) as solver:
#         try:
#             logging.info(f"Navigating to {target_url}...")
            
#             await page.goto(target_url, timeout=60_000, wait_until="domcontentloaded")
            
#             # 1. Handle the initial CAPTCHA check
#             await wait_and_solve_captcha(page, solver)

#             logging.info("Waiting for Cloudflare success screen to redirect...")
            
#             # 2. FORCE Playwright to wait until Cloudflare is completely gone
#             try:
#                 # Wait until the Cloudflare challenge div no longer exists on the page
#                 await page.wait_for_selector("#challenge-stage, .cf-turnstile", state="hidden", timeout=20_000)
#             except Exception:
#                 pass # Proceed anyway if it wasn't there

#             # 3. Wait strictly for the REAL page to load
#             try:
#                 # Based on your screenshots, the real page has addresses and a "Showing X - Y" text block
#                 await page.wait_for_selector("address, text='Showing', .list-group", timeout=15_000)
#             except Exception:
#                 logging.warning("Timeout waiting for real results. We might still be stuck on a loading screen.")

#             html_content = await page.content()
#             soup = BeautifulSoup(html_content, "lxml")
            
#             # 4. Strict Extractors (Removed the dangerous 'h2' fallback)
#             # We look for blocks that actually contain addresses or standard directory list items
#             cards = soup.select("article, div:has(address), .list-group-item") 
            
#             top_3_cards = cards[:3]
            
#             for card in top_3_cards:
#                 # We extract the raw text, but clean up the excessive spacing
#                 raw_text = card.get_text(separator="\n", strip=True)
                
#                 # Filter out garbage cards if any sneak in
#                 if len(raw_text) > 10: 
#                     person["results"].append({
#                         "raw_text_block": raw_text
#                     })
                
#             logging.info(f"Successfully extracted {len(person['results'])} actual records.")
                
#         except Exception as e:
#             logging.error(f"❌ Failed to scrape: {e}")
#         finally:
#             await page.close()
            
#     return person
# async def main():
#     results_data = []

#     async with AsyncCamoufox(
#         headless=HEADLESS,
#         humanize=True, # Critical for DataDome/Cloudflare mouse tracking
#         geoip=True
#     ) as browser:
        
#         logging.info("Camoufox Browser Launched. Starting scrape...")
        
#         for person in PEOPLE_TO_SEARCH:
#             result = await scrape_person(browser, person)
#             results_data.append(result)

#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(results_data, f, indent=2, ensure_ascii=False)
        
#     logging.info(f"✅ Scraping complete. Saved to {OUTPUT_FILE}")

# if __name__ == "__main__":
#     import sys
#     # Suppress Windows asyncio teardown errors
#     if sys.platform.startswith('win'):
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
#     try:
#         asyncio.run(main())
#     except Exception as e:
#         logging.error(f"Execution failed: {e}")

# import asyncio
# import json
# import logging
# import re
# from bs4 import BeautifulSoup
# from patchright.async_api import async_playwright
# from playwright_captcha import CaptchaType, ClickSolver, FrameworkType

# logging.basicConfig(level='INFO', format='[%(asctime)s] %(levelname)s - %(message)s', datefmt='%H:%M:%S')
# OUTPUT_FILE = "searchpeoplefree_results.json"

# PEOPLE_TO_SEARCH = [
#     {"first": "john", "last": "smith", "state": "ca", "city": "san-diego"},
#     {"first": "saksham", "last": "kaushish", "state": "mn", "city": "kandiyohi"}
# ]

# def build_search_url(person: dict) -> str:
#     base = f"https://www.searchpeoplefree.com/find/{person['first'].lower()}-{person['last'].lower()}"
#     if person.get("state"):
#         base += f"/{person['state'].lower()}"
#         if person.get("city"):
#             base += f"/{person['city'].lower().replace(' ', '-')}"
#     return base

# def clean_extracted_data(raw_text):
#     # Splits the giant block of text into individual person blocks
#     person_blocks = raw_text.split("More Free Details ⇒")
#     cleaned_results = []
    
#     for block in person_blocks:
#         if "Age" not in block:
#             continue
            
#         lines = [line.strip() for line in block.split('\n') if line.strip() and "{{" not in line]
        
#         person_data = {
#             "name": "N/A",
#             "age": "N/A",
#             "current_location": "N/A",
#             "past_locations": []
#         }
        
#         try:
#             # 1. Extract Age using Regex
#             age_match = re.search(r"Age\n(\d+)", "\n".join(lines))
#             if age_match:
#                 person_data["age"] = age_match.group(1)

#             # 2. Extract Name and Current Location
#             for i, line in enumerate(lines):
#                 if line.startswith("in ") and i > 0:
#                     person_data["name"] = lines[i-1]
#                     person_data["current_location"] = line.replace("in ", "").strip()
#                     break

#             # 3. Extract Past Addresses
#             if "Used to live in:" in lines:
#                 idx = lines.index("Used to live in:")
#                 if idx + 1 < len(lines):
#                     past_addresses = lines[idx + 1].split(',')
#                     person_data["past_locations"] = [addr.strip() for addr in past_addresses]
            
#             cleaned_results.append(person_data)
            
#         except Exception as e:
#             logging.debug(f"Skipping a block due to parsing error: {e}")
            
#     return cleaned_results[:3]

# async def scrape_person(page, person: dict):
#     target_url = build_search_url(person)
#     person["results"] = []
    
#     # Wrap the interaction in the solver
#     async with ClickSolver(framework=FrameworkType.PLAYWRIGHT, page=page) as solver:
#         try:
#             logging.info(f"Navigating to {target_url}...")
#             await page.goto(target_url, timeout=60_000)
            
#             # --- THE AUTO-SOLVER ---
#             try:
#                 if await page.query_selector("iframe[src*='cloudflare'], iframe[src*='datadome']"):
#                     logging.warning("⚠️ CAPTCHA detected! Engaging Auto-Solver...")
#                     await solver.solve_captcha(
#                         captcha_container=page,
#                         captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
#                         expected_content_selector="div" 
#                     )
#                     logging.info("✅ Auto-solver clicked the box!")
#                     await asyncio.sleep(4) 
#             except Exception as e:
#                 pass # Proceed if no captcha or solver fails gracefully
#             # -----------------------

#             logging.info("Waiting for page content to settle...")
#             try:
#                 await page.wait_for_function(
#                     "() => document.body.innerText.includes('Showing') || document.body.innerText.includes('0 People')", 
#                     timeout=15000
#                 )
#             except Exception:
#                 logging.warning("Timeout waiting for 'Showing' text. Proceeding to scrape.")

#             html_content = await page.content()
#             soup = BeautifulSoup(html_content, "lxml")
            
#             # Grab the raw data blocks
#             all_divs = soup.find_all("div")
#             cards = [div for div in all_divs if "Age" in div.get_text() and len(div.get_text()) > 20]
            
#             unique_texts = []
#             for card in cards:
#                 text = card.get_text(separator="\n", strip=True)
#                 if text not in unique_texts:
#                     unique_texts.append(text)
                    
#             top_3_raw = unique_texts[:3]
            
#             # Use the cleaner function to parse the messy text
#             for text_block in top_3_raw:
#                 structured_data = clean_extracted_data(text_block)
#                 person["results"].extend(structured_data)
                
#             # Strictly limit to 3 results per person
#             person["results"] = person["results"][:3]
#             logging.info(f"Extracted {len(person['results'])} clean records.")
            
#         except Exception as e:
#             logging.error(f"❌ Failed: {e}")
            
#     return person

# async def main():
#     results_data = []

#     async with async_playwright() as p:
#         logging.info("Connecting to existing Chrome session on port 9222...")
#         try:
#             # Hijack the running Chrome instance
#             browser = await p.chromium.connect_over_cdp("http://localhost:9222")
#             default_context = browser.contexts[0]
#             page = await default_context.new_page()
            
#             for person in PEOPLE_TO_SEARCH:
#                 result = await scrape_person(page, person)
#                 results_data.append(result)
#                 await asyncio.sleep(3) # Human delay between searches
                
#             await page.close()
            
#         except Exception as e:
#             logging.error(f"Failed to connect to Chrome. Make sure you ran the terminal command! Error: {e}")

#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(results_data, f, indent=2, ensure_ascii=False)
        
#     logging.info(f"✅ Scraping complete. Check {OUTPUT_FILE}.")

# if __name__ == "__main__":
#     asyncio.run(main())


# import asyncio
# import json
# import logging
# import re
# import os
# from bs4 import BeautifulSoup
# import random 
# from patchright.async_api import async_playwright
# from playwright_captcha import CaptchaType, ClickSolver, FrameworkType

# logging.basicConfig(level='INFO', format='[%(asctime)s] %(levelname)s - %(message)s', datefmt='%H:%M:%S')

# INPUT_FILE = "search_list.json"
# OUTPUT_FILE = "final_results.json"

# def build_search_url(person: dict) -> str:
#     base = f"https://www.searchpeoplefree.com/find/{person['first'].lower()}-{person['last'].lower()}"
#     if person.get("state"):
#         base += f"/{person['state'].lower()}"
#         if person.get("city"):
#             base += f"/{person['city'].lower().replace(' ', '-')}"
#     return base

# # Add this at the top of your script if not there already

# async def load_and_bypass(page, url, solver):
#     """Helper to load a page, handle WAF, and wait for actual content."""
#     logging.info(f"Navigating to {url}...")
#     await page.goto(url, timeout=60_000)
    
#     try:
#         if await page.query_selector("iframe[src*='cloudflare'], iframe[src*='datadome']"):
#             logging.warning("⚠️ CAPTCHA detected!")
            
#             try:
#                 await solver.solve_captcha(
#                     captcha_container=page,
#                     captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
#                     expected_content_selector="div" 
#                 )
#             except Exception:
#                 pass 

#             logging.info("Waiting for Cloudflare verification... injecting human telemetry.")
            
#             # --- THE JIGGLE TASK ---
#             # Moves the mouse randomly to build Cloudflare trust score
#             async def jiggle_mouse():
#                 for _ in range(30): 
#                     try:
#                         x = random.randint(100, 700)
#                         y = random.randint(100, 700)
#                         await page.mouse.move(x, y)
#                         await asyncio.sleep(1)
#                     except Exception:
#                         break

#             jiggle_task = asyncio.create_task(jiggle_mouse())

#             # --- THE WAIT & HARD FAIL ---
#             try:
#                 await page.wait_for_function(
#                     "() => document.title !== 'Just a moment...'", 
#                     timeout=30000 
#                 )
#                 jiggle_task.cancel() # Stop jiggling once cleared
#                 logging.info("✅ Cloudflare cleared!")
#                 await asyncio.sleep(2) 
#             except Exception:
#                 jiggle_task.cancel()
#                 logging.error("❌ Cloudflare timed out. Bot is stuck in purgatory.")
#                 # We raise an exception here to STOP the script from trying to scrape the WAF
#                 raise Exception("WAF_BLOCK") 
                
#     except Exception as e:
#         # If it's our custom WAF block, bubble it up so scrape_person fails gracefully
#         if str(e) == "WAF_BLOCK":
#             raise e
#         pass 

#     await page.wait_for_selector("body", timeout=15000)
#     return await page.content()
# async def scrape_person(page, person: dict):
#     target_url = build_search_url(person)
#     person["results"] = []
    
#     async with ClickSolver(framework=FrameworkType.PLAYWRIGHT, page=page) as solver:
#         try:
#             # 1. Load initial search page
#             html_content = await load_and_bypass(page, target_url, solver)
            
#             # --- INJECTED DEBUG LINES ---
#             os.makedirs("debug_logs", exist_ok=True) 
#             await page.screenshot(path=f"debug_logs/DEBUG_SCREENSHOT_{person['first']}.png")
#             with open(f"debug_logs/DEBUG_HTML_{person['first']}.html", "w", encoding="utf-8") as f:
#                 f.write(html_content)
#             # ----------------------------
            
#             soup = BeautifulSoup(html_content, "lxml")
            
#             # 2. Extract profile links from "More Free Details" buttons
#             profile_links = []
#             for a_tag in soup.find_all('a', href=True):
#                 if "More Free Details" in a_tag.get_text(strip=True):
#                     link = a_tag['href']
#                     if not link.startswith("http"):
#                         link = f"https://www.searchpeoplefree.com{link}"
#                     if link not in profile_links:
#                         profile_links.append(link)
            
#             top_3_links = profile_links[:3]
#             logging.info(f"Found {len(top_3_links)} detail profiles to check for {person['first']}.")

#             # 3. Visit each profile page for deep data
#             for i, profile_url in enumerate(top_3_links):
#                 # Generous sleep to prevent WAF ban from rapid navigation
#                 await asyncio.sleep(4) 
                
#                 profile_html = await load_and_bypass(page, profile_url, solver)
#                 profile_soup = BeautifulSoup(profile_html, "lxml")
                
#                 name = profile_soup.find("h1").get_text(strip=True) if profile_soup.find("h1") else "N/A"
#                 full_text = profile_soup.get_text(separator="\n", strip=True)
                
#                 age_match = re.search(r"Age\s*(\d+)", full_text)
#                 age = age_match.group(1) if age_match else "N/A"
                
#                 phones = list(set(re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", full_text)))
#                 emails = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", full_text)))

#                 person["results"].append({
#                     "Match_Rank": i + 1,
#                     "Name": name,
#                     "Age": age,
#                     "Phones": phones[:5], 
#                     "Emails": emails[:5],
#                     "Profile_URL": profile_url
#                 })

#         except Exception as e:
#             logging.error(f"❌ Failed processing {person['first']} {person['last']}: {e}")
            
#     return person
# async def main():
#     if not os.path.exists(INPUT_FILE):
#         logging.error(f"Input file '{INPUT_FILE}' not found! Please create it.")
#         return

#     with open(INPUT_FILE, "r", encoding="utf-8") as f:
#         try:
#             people_to_search = json.load(f)
#         except json.JSONDecodeError:
#             logging.error(f"Invalid JSON format in {INPUT_FILE}.")
#             return

#     results_data = []

#     async with async_playwright() as p:
#         logging.info("Patchright is launching Chrome with stealth patches...")
#         try:
#             # --- THE NEW LAUNCH METHOD ---
#             # We let Patchright launch a persistent session instead of CDP connecting
#             context = await p.chromium.launch_persistent_context(
#     user_data_dir="C:\\TempChromeProfile",
#     executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
#     headless=False,
#     ignore_https_errors=True,
#    proxy={
#     "server": "http://23.229.19.94:8689",
#     "username": "yegrcmfz",
#     "password": "z643uagujso5"
# },
#     args=["--disable-blink-features=AutomationControlled"],
#     viewport={"width": 1280, "height": 720}
# )
            
#             page = await context.new_page()
            
#             # Keep our stealth injection just in case
#             await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
#             # -----------------------------
            
#             for person in people_to_search:
#                 logging.info(f"Starting scrape for: {person['first']} {person['last']}")
#                 result = await scrape_person(page, person)
#                 results_data.append(result)
#                 await asyncio.sleep(4) 
                
#             await context.close()
            
#         except Exception as e:
#             logging.error(f"Failed to launch Chrome. Error: {e}")

#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump(results_data, f, indent=2, ensure_ascii=False)
        
#     logging.info(f"✅ Scraping complete. Check {OUTPUT_FILE}.")
# if __name__ == "__main__":
#     asyncio.run(main())

# import json
# import logging
# import time
# import re
# import requests
# from bs4 import BeautifulSoup
# import undetected_chromedriver as uc
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.by import By

# SCRAPINGBEE_API_KEY = "HFL1A1GQGMH5KUGUZCGDMVZ9JE2UBULUBZEBMP8T3TB2Y0IZ8JQ6E7ZUKX6WCVUD4G9YGA3Y8YT1S1EC"
# OUTPUT_FILE = "test_result_searchpeoplefree.json"
# DEBUG_HTML_FILE = "debug_search_page.html"  # <-- saves raw HTML so you can inspect it

# TEST_PERSON = {
#     "first": "saksham",
#     "last": "kaushish",
#     "state": "mn",
#     "city": "kandiyohi"
# }

# logging.basicConfig(level='INFO', format='[%(asctime)s] %(levelname)s - %(message)s', datefmt='%H:%M:%S')


# def build_search_url(person: dict) -> str:
#     base = f"https://www.searchpeoplefree.com/find/{person['first'].lower()}-{person['last'].lower()}"
#     if person.get("state"):
#         base += f"/{person['state'].lower()}"
#         # if person.get("city"):
#         #     base += f"/{person['city'].lower().replace(' ', '-')}"
#     return base

# def fetch_with_uc(url: str) -> str:
#     logging.info(f"Fetching with undetected-chromedriver: {url}")
    
#     options = uc.ChromeOptions()
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     # Remove headless for first test — some sites detect headless
#     # options.add_argument("--headless=new")
    
#     driver = uc.Chrome(options=options, version_main=147)
#     try:
#         driver.get(url)
#         # Wait until actual content loads (not a challenge page)
#         WebDriverWait(driver, 20).until(
#             lambda d: "searchpeoplefree" in d.current_url and 
#                       "checking" not in d.page_source.lower()
#         )
#         import time
#         time.sleep(3)  # Let JS finish rendering results
#         html = driver.page_source
#         return html
#     except Exception as e:
#         logging.error(f"UC driver error: {e}")
#         return None
#     finally:
#         driver.quit()


# # def fetch_with_scrapingbee(url: str, retries: int = 3):
# #     logging.info(f"Fetching: {url}")

# #     for attempt in range(1, retries + 1):
# #         params = {
# #     "api_key": SCRAPINGBEE_API_KEY,
# #     "url": url,
# #     "render_js": "True",
# #     "premium_proxy": "True",
# #     "country_code": "us",
# #     "wait": "8000",
# #     "device": "desktop",
# #     "block_resources": "False",   # <-- ADD THIS (ScrapingBee told you to)
# # }

# #         try:
# #             response = requests.get(
# #                 "https://app.scrapingbee.com/api/v1/",
# #                 params=params,
# #                 timeout=90
# #             )

# #             if response.status_code == 200:
# #                 logging.info(f"Got response ({len(response.text)} chars)")
# #                 return response.text

# #             try:
# #                 error_data = response.json()
# #                 reason = error_data.get("reason", "")
# #             except ValueError:
# #                 reason = response.text

# #             if response.status_code == 500 and "451" in str(reason):
# #                 logging.warning(f"Attempt {attempt}/{retries}: 451 Legal Block. Retrying...")
# #                 time.sleep(3)
# #                 continue

# #             logging.error(f"ScrapingBee error (HTTP {response.status_code}): {response.text[:300]}")
# #             return None

# #         except requests.exceptions.RequestException as e:
# #             logging.error(f"Network error: {e}")
# #             if attempt == retries:
# #                 return None

# #     logging.error("All retries exhausted.")
# #     return None


# def find_profile_links(soup: BeautifulSoup, base_url: str) -> list:
#     """
#     FIXED: broader link detection — searches by URL pattern, not button text.
#     searchpeoplefree.com profile URLs look like /people/firstname-lastname/ID
#     """
#     profile_links = []
#     seen = set()

#     for a_tag in soup.find_all('a', href=True):
#         href = a_tag['href']
#         # Match profile-style URLs — adjust this pattern if needed after seeing debug HTML
#         if re.search(r'/people/|/profile/', href, re.IGNORECASE):
#             full_link = href if href.startswith("http") else f"https://www.searchpeoplefree.com{href}"
#             if full_link not in seen:
#                 seen.add(full_link)
#                 profile_links.append(full_link)

#     # Fallback: catch any link with the person's name in the URL
#     if not profile_links:
#         logging.warning("Pattern match found nothing — falling back to name-based URL search")
#         for a_tag in soup.find_all('a', href=True):
#             href = a_tag['href'].lower()
#             if TEST_PERSON['first'] in href and TEST_PERSON['last'] in href:
#                 full_link = a_tag['href'] if a_tag['href'].startswith("http") else f"https://www.searchpeoplefree.com{a_tag['href']}"
#                 if full_link not in seen:
#                     seen.add(full_link)
#                     profile_links.append(full_link)

#     return profile_links


# def scrape_person(person: dict):
#     target_url = build_search_url(person)
#     person["results"] = []

#     try:
#         html_content = fetch_with_uc(target_url)
#         if not html_content:
#             logging.warning("Failed to retrieve search page.")
#             return person

#         # Save raw HTML so you can inspect what was actually returned
#         with open(DEBUG_HTML_FILE, "w", encoding="utf-8") as f:
#             f.write(html_content)
#         logging.info(f"Raw HTML saved to {DEBUG_HTML_FILE} — open it in a browser to inspect")

#         soup = BeautifulSoup(html_content, "lxml")
#         page_text = soup.get_text().lower()

#         if "cloudflare" in page_text or "attention required" in page_text or "checking your browser" in page_text:
#             logging.error("BLOCKED: Cloudflare challenge page returned. ScrapingBee didn't bypass it.")
#             return person

#         if "captcha" in page_text:
#             logging.error("BLOCKED: CAPTCHA page returned.")
#             return person

#         profile_links = find_profile_links(soup, target_url)
#         top_links = profile_links[:3]
#         logging.info(f"Found {len(top_links)} profile links to visit.")

#         if not top_links:
#             logging.warning("No profile links found. Check debug_search_page.html to see what was returned.")

#         for i, profile_url in enumerate(top_links):
#             profile_html = fetch_with_uc(profile_url)
#             if not profile_html:
#                 continue

#             profile_soup = BeautifulSoup(profile_html, "lxml")
#             full_text = profile_soup.get_text(separator="\n", strip=True)

#             name = profile_soup.find("h1")
#             name = name.get_text(strip=True) if name else "N/A"

#             age_match = re.search(r"(?:Age|Born)[\s:]*(\d{2})", full_text, re.IGNORECASE)
#             age = age_match.group(1) if age_match else "N/A"

#             phones = list(set(re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", full_text)))
#             emails = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", full_text)))

#             person["results"].append({
#                 "Match_Rank": i + 1,
#                 "Name": name,
#                 "Age": age,
#                 "Phones": phones[:5],
#                 "Emails": emails[:5],
#                 "Profile_URL": profile_url
#             })

#     except Exception as e:
#         logging.error(f"Scraping failed: {e}", exc_info=True)

#     return person


# if __name__ == "__main__":
#     logging.info("--- Starting Test ---")
#     final_data = scrape_person(TEST_PERSON)

#     with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#         json.dump([final_data], f, indent=2, ensure_ascii=False)

#     logging.info(f"Done. Results in {OUTPUT_FILE}")
#     logging.info(f"If results are empty, open {DEBUG_HTML_FILE} to see what was returned and share it.")
"""
searchpeoplefree.com — production scraper
Architecture : 3-worker pool, sharing ONE persistent Camoufox browser profile
               cf_clearance cookie is preserved across runs via cookie file
               Fixed sticky proxy session keeps same IP → cf_clearance stays valid
"""

import asyncio
import json
import logging
import re
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox

# ══════════════════════════════════════════════════════════════
#  CONFIG  — edit before running
# ══════════════════════════════════════════════════════════════
IPROYAL_USERNAME    = "16H4QGoZ0UmnaEB4"
IPROYAL_PASSWORD    = "q1dYSNtI0heQXxRA_country-us_state-arizona_streaming-1"
IPROYAL_HOST        = "geo.iproyal.com"
IPROYAL_PORT        = 11202
STICKY_LIFETIME_MIN = 60

FIXED_SESSION_ID    = "persistsess01"

NUM_WORKERS         = 3
TOP_N_PROFILES      = 3
MAX_WAF_RETRIES     = 2

INPUT_FILE          = "search_list.json"
OUTPUT_FILE         = "final_results.json"
DEBUG_DIR           = Path("debug_logs")
PROFILE_DIR         = Path("browser_profile")
COOKIE_FILE         = PROFILE_DIR / "cookies.json"

# Delays (seconds)
DELAY_PROFILES      = (5, 10)
DELAY_RETRY         = (12, 20)

# Timeouts (ms)
GOTO_TIMEOUT        = 60_000
CONTENT_TIMEOUT     = 25_000

# ══════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def wlog(worker_id: int, level: str, msg: str):
    getattr(log, level)(f"[W{worker_id}] {msg}")


# ══════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════
@dataclass
class ProfileResult:
    match_rank:  int
    name:        str  = "N/A"
    age:         str  = "N/A"
    phones:      list = field(default_factory=list)
    emails:      list = field(default_factory=list)
    addresses:   list = field(default_factory=list)
    relatives:   list = field(default_factory=list)
    profile_url: str  = ""


@dataclass
class PersonRecord:
    first:   str
    last:    str  = ""          # optional — handles single-name searches
    state:   str  = ""
    city:    str  = ""
    results: list = field(default_factory=list)
    error:   str  = ""


# ══════════════════════════════════════════════════════════════
#  PROXY — ONE fixed session shared across all workers
# ══════════════════════════════════════════════════════════════
def make_persistent_proxy() -> dict:
    password = (
        f"{IPROYAL_PASSWORD}"
        f"_session-{FIXED_SESSION_ID}"
        f"_lifetime-{STICKY_LIFETIME_MIN}m"
        f"_country-us"
    )
    return {
        "server":   f"http://{IPROYAL_HOST}:{IPROYAL_PORT}",
        "username": IPROYAL_USERNAME,
        "password": password,
    }


# ══════════════════════════════════════════════════════════════
#  COOKIE HELPERS — persist cf_clearance across runs
# ══════════════════════════════════════════════════════════════
async def load_cookies(page, wid: int) -> None:
    """Load saved cookies into the page context if cookie file exists."""
    if COOKIE_FILE.exists():
        try:
            with open(COOKIE_FILE, encoding="utf-8") as f:
                cookies = json.load(f)
            if cookies:
                await page.context.add_cookies(cookies)
                wlog(wid, "info", f"🍪 Loaded {len(cookies)} saved cookies — CAPTCHA should be skipped")
            else:
                wlog(wid, "warning", "Cookie file is empty — CAPTCHA may appear")
        except Exception as e:
            wlog(wid, "warning", f"Could not load cookies: {e}")
    else:
        wlog(wid, "info", "🆕 No saved cookies found — solve CAPTCHA manually when browser opens")


async def save_cookies(page, wid: int) -> None:
    """Save current cookies to file so cf_clearance survives next run."""
    try:
        cookies = await page.context.cookies()
        PROFILE_DIR.mkdir(exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        cf_names = [c["name"] for c in cookies if "cf" in c["name"].lower()]
        wlog(wid, "info", f"🍪 Saved {len(cookies)} cookies (CF cookies: {cf_names})")
    except Exception as e:
        wlog(wid, "warning", f"Could not save cookies: {e}")


# ══════════════════════════════════════════════════════════════
#  URL BUILDER — handles empty last name
# ══════════════════════════════════════════════════════════════
def build_search_url(p: PersonRecord) -> str:
    if p.last and p.last.strip():
        slug = f"{p.first.lower()}-{p.last.lower()}"
    else:
        slug = p.first.lower()

    url = f"https://www.searchpeoplefree.com/find/{slug}"
    if p.state:
        url += f"/{p.state.lower()}"
        if p.city:
            url += f"/{p.city.lower().replace(' ', '-')}"
    return url


# ══════════════════════════════════════════════════════════════
#  WAF / CLOUDFLARE TURNSTILE SOLVER
# ══════════════════════════════════════════════════════════════
async def _is_waf_page(page) -> bool:
    title = (await page.title()).lower()
    if any(t in title for t in ("just a moment", "please wait",
                                "attention required", "access denied")):
        return True
    for sel in (
        "#challenge-stage", ".cf-turnstile", "#cf-please-wait",
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='datadome']",
        "iframe[src*='geo.captcha-delivery.com']",
    ):
        if await page.query_selector(sel):
            return True
    return False


async def _click_turnstile_checkbox(page, wid: int) -> bool:
    await asyncio.sleep(3)

    outer_selectors = [
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[title*='Widget containing']",
        ".cf-turnstile iframe",
        "#cf-turnstile iframe",
        "iframe[src*='turnstile']",
    ]

    outer_frame = None
    for sel in outer_selectors:
        try:
            outer_frame = await page.query_selector(sel)
            if outer_frame:
                wlog(wid, "info", f"  Turnstile iframe found via: {sel}")
                break
        except Exception:
            continue

    if not outer_frame:
        wlog(wid, "warning", "  No Turnstile iframe — may be non-interactive challenge")
        return False

    try:
        frame = await outer_frame.content_frame()
        if not frame:
            wlog(wid, "warning", "  Could not enter iframe content frame")
            return False

        checkbox_selectors = [
            ".mark",
            "input[type='checkbox']",
            "label.ctp-checkbox-label",
            "#challenge-stage input",
        ]
        checkbox = None
        for sel in checkbox_selectors:
            try:
                checkbox = await frame.query_selector(sel)
                if checkbox:
                    wlog(wid, "info", f"  Checkbox found via: {sel}")
                    break
            except Exception:
                continue

        if not checkbox:
            wlog(wid, "warning", "  No checkbox found — clicking iframe centre")
            box = await outer_frame.bounding_box()
            if box:
                cx = box["x"] + box["width"]  / 2
                cy = box["y"] + box["height"] / 2
                await page.mouse.move(cx - 40, cy - 20)
                await asyncio.sleep(random.uniform(0.3, 0.7))
                await page.mouse.move(cx, cy)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.mouse.click(cx, cy)
                return True

        box = await checkbox.bounding_box()
        if box:
            cx = box["x"] + box["width"]  / 2
            cy = box["y"] + box["height"] / 2
            await page.mouse.move(cx - 80, cy - 40)
            await asyncio.sleep(random.uniform(0.2, 0.5))
            await page.mouse.move(cx - 15, cy - 8)
            await asyncio.sleep(random.uniform(0.1, 0.25))
            await page.mouse.click(cx, cy)
            wlog(wid, "info", "  ✅ Clicked Turnstile checkbox")
            return True

    except Exception as e:
        wlog(wid, "error", f"  Turnstile click error: {e}")

    return False


async def _wait_for_clearance(page) -> bool:
    try:
        await page.wait_for_function(
            """() => {
                const t = document.title.toLowerCase();
                return !t.includes('just a moment') &&
                       !t.includes('please wait')   &&
                       !t.includes('attention required') &&
                       !t.includes('access denied');
            }""",
            timeout=CONTENT_TIMEOUT,
        )
        return True
    except Exception:
        return False


async def _solve_waf(page, wid: int) -> bool:
    wlog(wid, "warning", "⚠  WAF detected — starting Turnstile solver…")

    clicked = await _click_turnstile_checkbox(page, wid)

    if clicked:
        wlog(wid, "info", "  Waiting for Cloudflare validation…")
        await asyncio.sleep(2)
        if await _wait_for_clearance(page):
            wlog(wid, "info", "✅ WAF cleared after checkbox click!")
            await asyncio.sleep(2)
            # Save cookies immediately after solving so they're not lost
            await save_cookies(page, wid)
            return True
        wlog(wid, "warning", "  Click didn't clear — trying passive wait…")

    await asyncio.sleep(6)
    if await _wait_for_clearance(page):
        wlog(wid, "info", "✅ WAF cleared passively")
        await save_cookies(page, wid)
        return True

    wlog(wid, "error", "❌ WAF not cleared.")
    return False


# ══════════════════════════════════════════════════════════════
#  NAVIGATION WRAPPER
# ══════════════════════════════════════════════════════════════
async def safe_goto(page, url: str, wid: int) -> str:
    for attempt in range(1, MAX_WAF_RETRIES + 2):
        wlog(wid, "info", f"→ GET {url}  (attempt {attempt})")
        try:
            await page.goto(url, timeout=GOTO_TIMEOUT, wait_until="domcontentloaded")
        except Exception as e:
            raise RuntimeError(f"Navigation failed: {e}")

        await asyncio.sleep(2)

        if not await _is_waf_page(page):
            await page.wait_for_selector("body", timeout=10_000)
            return await page.content()

        cleared = await _solve_waf(page, wid)
        if cleared:
            await page.wait_for_selector("body", timeout=10_000)
            return await page.content()

        if attempt <= MAX_WAF_RETRIES:
            delay = random.uniform(*DELAY_RETRY)
            wlog(wid, "warning", f"  Sleeping {delay:.1f}s then retrying…")
            await asyncio.sleep(delay)

    raise RuntimeError(f"WAF persisted after {MAX_WAF_RETRIES + 1} attempts on {url}")


# ══════════════════════════════════════════════════════════════
#  PARSERS
# ══════════════════════════════════════════════════════════════
_PROFILE_URL_RE = [
    re.compile(r"/find/[a-z]+-[a-z]+/\w+/\d+"),
    re.compile(r"/people/"),
    re.compile(r"/profile/"),
    re.compile(r"/s/[a-zA-Z]"),
    re.compile(r"/details"),
]

_PHONE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_AGE   = re.compile(r"(?:Age|Born)[^\d]*(\d{2,3})", re.I)


def extract_more_details_links(html: str, base: str = "https://www.searchpeoplefree.com") -> list:
    """Targets 'More Free Details' buttons specifically."""
    soup = BeautifulSoup(html, "lxml")
    found, seen = [], set()

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if "more free details" in text or "free details" in text:
            href = a["href"]
            full = href if href.startswith("http") else base + href
            if full not in seen:
                seen.add(full)
                found.append(full)

    for btn in soup.select("a.btn, a[class*='detail'], a[class*='more']"):
        href = btn.get("href", "")
        if href:
            full = href if href.startswith("http") else base + href
            if full not in seen:
                seen.add(full)
                found.append(full)

    return found


def extract_profile_links(html: str, base: str = "https://www.searchpeoplefree.com") -> list:
    """URL-pattern fallback if button extractor finds nothing."""
    soup = BeautifulSoup(html, "lxml")
    found, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(p.search(href) for p in _PROFILE_URL_RE):
            full = href if href.startswith("http") else base + href
            if full not in seen:
                seen.add(full)
                found.append(full)
    return found


def parse_profile(html: str, url: str, rank: int) -> ProfileResult:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n", strip=True)

    name = "N/A"
    h1   = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    else:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            name = og["content"].strip()

    age_m = _AGE.search(text)
    age   = age_m.group(1) if age_m else "N/A"

    phones = list(dict.fromkeys(_PHONE.findall(text)))[:5]
    emails = list(dict.fromkeys(_EMAIL.findall(text)))[:5]

    addresses = []
    for tag in soup.select("address, [class*='address'], [class*='location']"):
        addr = tag.get_text(separator=" ", strip=True)
        if len(addr) > 5 and addr not in addresses:
            addresses.append(addr)

    relatives = []
    for node in soup.find_all(string=re.compile(r"relative|associate|family", re.I)):
        parent = node.find_parent()
        if parent:
            rt = parent.get_text(separator=", ", strip=True)
            if rt and rt not in relatives:
                relatives.append(rt)

    return ProfileResult(
        match_rank=rank, name=name, age=age,
        phones=phones, emails=emails,
        addresses=addresses[:5], relatives=relatives[:5],
        profile_url=url,
    )


# ══════════════════════════════════════════════════════════════
#  SCRAPE ONE PERSON
# ══════════════════════════════════════════════════════════════
async def scrape_person(page, person: PersonRecord, wid: int) -> PersonRecord:
    # handle empty last name in debug slug
    last_part  = person.last.strip() if person.last and person.last.strip() else "unknown"
    slug       = f"{person.first}_{last_part}"
    search_url = build_search_url(person)
    DEBUG_DIR.mkdir(exist_ok=True)

    try:
        # ── search results page ──────────────────────────────
        search_html = await safe_goto(page, search_url, wid)
        (DEBUG_DIR / f"w{wid}_{slug}_search.html").write_text(search_html, encoding="utf-8")
        await page.screenshot(path=str(DEBUG_DIR / f"w{wid}_{slug}_search.png"))

        # ── extract links — button-targeted first, URL-pattern fallback ──
        links = extract_more_details_links(search_html)
        if not links:
            wlog(wid, "warning", "No 'More Free Details' buttons — falling back to URL patterns")
            links = extract_profile_links(search_html)

        links = links[:TOP_N_PROFILES]

        if not links:
            wlog(wid, "warning", f"No profile links for {person.first} {person.last or '(no last name)'}")
            person.error = "no_profile_links"
            return person

        wlog(wid, "info", f"Found {len(links)} profiles for {person.first} {person.last or '(no last name)'}")

        # ── visit each profile page ──────────────────────────
        for rank, purl in enumerate(links, start=1):
            await asyncio.sleep(random.uniform(*DELAY_PROFILES))
            try:
                phtml  = await safe_goto(page, purl, wid)
                (DEBUG_DIR / f"w{wid}_{slug}_profile_{rank}.html").write_text(
                    phtml, encoding="utf-8"
                )
                result = parse_profile(phtml, purl, rank)
                person.results.append(asdict(result))
                wlog(wid, "info",
                     f"  ✓ rank {rank}: {result.name}, age {result.age}, "
                     f"{len(result.phones)} phones")
            except RuntimeError as e:
                wlog(wid, "error", f"  ✗ profile {rank} blocked: {e}")

    except RuntimeError as e:
        wlog(wid, "error", f"Blocked: {person.first} {person.last or ''} — {e}")
        person.error = "waf_block"
    except Exception as e:
        wlog(wid, "error", f"Error: {person.first} {person.last or ''} — {e}")
        person.error = str(e)

    return person


# ══════════════════════════════════════════════════════════════
#  PROGRESS REPORTER
# ══════════════════════════════════════════════════════════════
async def progress_reporter(done_counter: list, total: int, stop_event: asyncio.Event):
    while not stop_event.is_set():
        done = done_counter[0]
        log.info(f"📊 Progress: {done}/{total} complete  ({total - done} remaining)")
        await asyncio.sleep(30)


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
async def main():
    if not Path(INPUT_FILE).exists():
        log.error(f"'{INPUT_FILE}' not found.")
        log.error('Example: [{"first":"john","last":"smith","state":"ca","city":"san-diego"}]')
        log.error('Last name is optional: [{"first":"saksham","state":"ks","city":"kansas-city"}]')
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        raw = json.load(f)

    people = [PersonRecord(**p) for p in raw]
    total  = len(people)
    log.info(f"Loaded {total} people — launching {NUM_WORKERS} workers")

    PROFILE_DIR.mkdir(exist_ok=True)

    proxy = make_persistent_proxy()
    log.info(f"Using fixed proxy session: {FIXED_SESSION_ID}")

    if COOKIE_FILE.exists():
        log.info(f"✅ Cookie file found at {COOKIE_FILE} — CAPTCHA should be skipped")
    else:
        log.info("⚠️  No cookie file — you will need to solve CAPTCHA manually on first run")

    queue:        asyncio.Queue  = asyncio.Queue()
    for p in people:
        await queue.put(p)

    results:      list           = []
    lock:         asyncio.Lock   = asyncio.Lock()
    done_counter: list           = [0]
    stop_event:   asyncio.Event  = asyncio.Event()

    async def tracked_worker(wid: int):
        wlog(wid, "info", "Worker started")

        while True:
            try:
                person: PersonRecord = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            wlog(wid, "info", f"Processing {person.first} {person.last or '(no last name)'}")

            result = person
            try:
                async with AsyncCamoufox(
                    headless=False,
                    humanize=True,
                    geoip=True,
                    proxy=proxy,
                ) as browser:
                    page = await browser.new_page()

                    # Load saved cookies — skips CAPTCHA if cf_clearance is valid
                    await load_cookies(page, wid)

                    await page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )

                    result = await scrape_person(page, person, wid)

                    # Save cookies after each person — keeps cf_clearance fresh
                    await save_cookies(page, wid)

            except Exception as e:
                wlog(wid, "error", f"Browser launch error: {e}")
                person.error = f"browser_error: {e}"
                result = person

            finally:
                queue.task_done()

            async with lock:
                results.append(asdict(result))
                done_counter[0] += 1

            wlog(wid, "info",
                 f"Done: {person.first} {person.last or ''} "
                 f"({len(result.results)} profiles found)")

        wlog(wid, "info", "Queue empty — worker exiting.")

    worker_tasks = [
        asyncio.create_task(tracked_worker(wid))
        for wid in range(1, NUM_WORKERS + 1)
    ]
    reporter_task = asyncio.create_task(
        progress_reporter(done_counter, total, stop_event)
    )

    await asyncio.gather(*worker_tasks)
    stop_event.set()
    reporter_task.cancel()

    # Sort output to match original input order — handles empty last name
    order = {f"{p.first}_{p.last or ''}": i for i, p in enumerate(people)}
    results.sort(key=lambda r: order.get(f"{r['first']}_{r.get('last', '')}", 999))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total_profiles = sum(len(r["results"]) for r in results)
    blocked        = sum(1 for r in results if r.get("error") == "waf_block")
    no_links       = sum(1 for r in results if r.get("error") == "no_profile_links")

    log.info("═" * 50)
    log.info(f"✅ Complete — {total} people processed")
    log.info(f"   Profiles found : {total_profiles}")
    log.info(f"   WAF blocks     : {blocked}")
    log.info(f"   No links found : {no_links}")
    log.info(f"   Output         : {OUTPUT_FILE}")
    log.info("═" * 50)


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            finally:
                loop.close()
    else:
        asyncio.run(main())