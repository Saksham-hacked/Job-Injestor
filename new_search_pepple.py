# import asyncio
# import logging
# import os
# import random

# from camoufox import AsyncCamoufox
# from playwright_captcha import CaptchaType, ClickSolver, FrameworkType
# from playwright_captcha.utils.camoufox_add_init_script.add_init_script import get_addon_path

# logging.basicConfig(
#     level='INFO',
#     format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )

# # ─────────────────────────────────────────────────────────────────────────────
# # IPRoyal Rotating Proxy Configuration
# # ─────────────────────────────────────────────────────────────────────────────
# PROXY_HOST = "geo.iproyal.com"
# PROXY_PORT = 11202
# PROXY_USER = "16H4QGoZ0UmnaEB4"
# PROXY_PASS = "q1dYSNtI0heQXxRA_country-us_state-arizona_streaming-1"

# # ─────────────────────────────────────────────────────────────────────────────
# # TARGET URL — change this to your actual target
# # ─────────────────────────────────────────────────────────────────────────────
# TARGET_URL = "https://searchpeoplefree.com/find/saksham/mn/kandiyohi"

# # Selector visible on the REAL page after Cloudflare clears
# EXPECTED_SELECTOR = "#root"


# def get_proxy_config() -> dict:
#     return {
#         "server":   f"http://{PROXY_HOST}:{PROXY_PORT}",
#         "username": PROXY_USER,
#         "password": PROXY_PASS,
#     }


# async def solve_interstitial() -> None:
#     ADDON_PATH = get_addon_path()
#     proxy_config = get_proxy_config()

#     logging.info(f"Using proxy  : {proxy_config['server']}")
#     logging.info(f"Target URL   : {TARGET_URL}")
#     logging.info(f"Addon path   : {ADDON_PATH}")

#     async with AsyncCamoufox(
#         # ── Visibility ───────────────────────────────────────────────────────
#         # headless=False is CRITICAL — Cloudflare's JS challenge detects headless
#         # mode even in Camoufox when the challenge is strict.
#         headless=False,

#         # ── Stealth / humanisation ────────────────────────────────────────────
#         geoip=True,       # Spoof geolocation to match the proxy exit node IP
#         humanize=True,    # Randomise mouse movements, scroll behaviour, timing

#         # ── Required for add_init_script workaround ───────────────────────────
#         i_know_what_im_doing=True,
#         config={'forceScopeAccess': True},
#         disable_coop=True,
#         main_world_eval=True,
#         addons=[os.path.abspath(ADDON_PATH)],

#         # ── IPRoyal proxy ─────────────────────────────────────────────────────
#         proxy=proxy_config,
#     ) as browser:

#         context = await browser.new_context(
#             # Mimic a real viewport size — headless default (1280x720) can be a signal
#             viewport={"width": random.randint(1280, 1920), "height": random.randint(768, 1080)},
#         )
#         page = await context.new_page()

#         # ── Extra human-like delay before navigating ──────────────────────────
#         await asyncio.sleep(random.uniform(1.5, 3.0))

#         framework = FrameworkType.CAMOUFOX

#         async with ClickSolver(framework=framework, page=page) as solver:
#             await page.goto(TARGET_URL, wait_until="domcontentloaded")

#             # Give Cloudflare time to fully render the interstitial page
#             # (increase to 10+ if your connection/proxy is slow)
#             await asyncio.sleep(8)

#             logging.info("Attempting to solve Cloudflare interstitial...")
#             await solver.solve_captcha(
#                 captcha_container=page,
#                 captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
#                 expected_content_selector=EXPECTED_SELECTOR,
#             )

#             # Wait for the page to fully transition after the challenge passes
#             await asyncio.sleep(5)

#         # ── Verify success ────────────────────────────────────────────────────
#         try:
#             await page.locator(
#                 '//p[text()="Captcha is passed successfully!"]'
#             ).wait_for(timeout=15_000)
#             logging.info("✅ Captcha is passed successfully!")
#         except Exception as e:
#             # Dump the page title to help diagnose what Cloudflare returned
#             title = await page.title()
#             logging.error(f"❌ Captcha solving failed: {e}")
#             logging.error(f"   Page title at failure: '{title}'")
#             logging.error(
#                 "   Possible causes:\n"
#                 "   1. Proxy IP is flagged by Cloudflare (try residential proxies)\n"
#                 "   2. Cloudflare issued a JS challenge, not just a checkbox\n"
#                 "   3. expected_content_selector '#root' is wrong for this page\n"
#                 "   4. Increase the asyncio.sleep(8) wait above if the page loads slowly"
#             )
#             return
#         finally:
#             await context.close()

#     logging.info("Finished")


# if __name__ == "__main__":
#     asyncio.run(solve_interstitial())



# import asyncio
# import logging
# import os
# import random
# import string

# from camoufox import AsyncCamoufox
# from playwright_captcha import CaptchaType, ClickSolver, FrameworkType
# from playwright_captcha.utils.camoufox_add_init_script.add_init_script import get_addon_path

# # Configure Logging
# logging.basicConfig(
#     level='INFO',
#     format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )

# # ─────────────────────────────────────────────────────────────────────────────
# # Proxy Configuration
# # ─────────────────────────────────────────────────────────────────────────────
# PROXY_HOST = "geo.iproyal.com"
# PROXY_PORT = 11202
# PROXY_USER = "16H4QGoZ0UmnaEB4"

# # ─────────────────────────────────────────────────────────────────────────────
# # Target URL & Validation Elements
# # ─────────────────────────────────────────────────────────────────────────────
# TARGET_URL = "https://searchpeoplefree.com/find/saksham/mn/kandiyohi"

# EXPECTED_SELECTOR = "div.container"  # Standard layout wrapper
# REAL_PAGE_HEADER = "h1"              # The main title element of the real site


# def get_proxy_config() -> dict:
#     # Generate a random 8-character string for the IPRoyal session ID
#     # This ensures the proxy IP stays sticky (does not rotate) for this entire script run.
#     # If the IP changes halfway through the Cloudflare challenge, it will infinite loop.
#     session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
#     # Append the session flag to your IPRoyal password string
#     base_pass = "q1dYSNtI0heQXxRA_country-us_state-arizona_streaming-1"
#     sticky_pass = f"{base_pass}_session-{session_id}"
    
#     return {
#         "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
#         "username": PROXY_USER,
#         "password": sticky_pass,
#     }


# async def run_scraper() -> None:
#     addon_path = get_addon_path()
#     proxy_config = get_proxy_config()

#     logging.info(f"Using proxy : {proxy_config['server']} (Sticky Session Enabled)")
#     logging.info(f"Target URL  : {TARGET_URL}")

#     # Initialize Camoufox Browser Context
#     async with AsyncCamoufox(
#         headless=False,
#         geoip=True,
#         humanize=False, # Must be False so ClickSolver controls the mouse perfectly
#         i_know_what_im_doing=True,
#         config={'forceScopeAccess': True},
#         disable_coop=True,
#         main_world_eval=True,
#         addons=[os.path.abspath(addon_path)],
#         proxy=proxy_config,
#     ) as browser:

#         # Use strict, standard resolutions. Random dimensions flag Cloudflare.
#         standard_resolutions = [
#             {"width": 1920, "height": 1080},
#             {"width": 1366, "height": 768},
#             {"width": 1536, "height": 864},
#             {"width": 1440, "height": 900}
#         ]
#         selected_viewport = random.choice(standard_resolutions)

#         context = await browser.new_context(viewport=selected_viewport)
#         page = await context.new_page()

#         # Initial human-like delay
#         await asyncio.sleep(random.uniform(1.0, 2.5))

#         framework = FrameworkType.CAMOUFOX

#         async with ClickSolver(framework=framework, page=page) as solver:
#             logging.info("Navigating to target page...")
#             await page.goto(TARGET_URL, wait_until="domcontentloaded")

#             # CRITICAL: Let Cloudflare's background scripts fully execute and generate 
#             # the backend token before trying to click. If clicked too early, it loops.
#             logging.info("Waiting for Cloudflare widget to settle completely...")
#             await asyncio.sleep(random.uniform(6.0, 8.0))

#             logging.info("Attempting to bypass Cloudflare challenge...")
#             try:
#                 await solver.solve_captcha(
#                     captcha_container=page,
#                     captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
#                     expected_content_selector=EXPECTED_SELECTOR,
#                 )
#                 # Wait for the post-challenge redirect transition
#                 await asyncio.sleep(5)
#             except Exception as solver_err:
#                 logging.warning(f"Solver encountered an alert/error: {solver_err}")

#         # ── Verify Target Data ────────────────────────────────────────────────
#         try:
#             # Wait for the actual webpage header to confirm bypass
#             await page.wait_for_selector(REAL_PAGE_HEADER, timeout=10_000)
            
#             page_title = await page.title()
#             logging.info(f"✅ Bypassed Cloudflare successfully!")
#             logging.info(f"📄 Arrived at page title: '{page_title}'")
            
#             # --- Capture your data here ---
#             # page_content = await page.content()
            
#         except Exception as e:
#             title = await page.title()
#             logging.error(f"❌ Failed to confirm arrival on target landing page: {e}")
#             logging.error(f"Current page title at roadblock: '{title}'")
#         finally:
#             await context.close()

#     logging.info("Session finished, browser closed.")


# if __name__ == "__main__":
#     asyncio.run(run_scraper())



# //session stored and used in two different runs of the script, to demonstrate how to save a session after solving Cloudflare and then reuse it later for automated scraping without manual intervention.
# import asyncio
# import logging
# import os

# from camoufox import AsyncCamoufox
# from playwright.async_api import Error as PlaywrightError

# logging.basicConfig(
#     level='INFO',
#     format='[%(asctime)s] %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )

# # ─────────────────────────────────────────────────────────────────────────────
# # Configuration
# # ─────────────────────────────────────────────────────────────────────────────
# TARGET_URL = "https://searchpeoplefree.com/find/saksham/mn/kandiyohi"
# SESSION_FILE = "cloudflare_session.json"
# UA_FILE = "user_agent.txt"  # We now save the User-Agent here

# # Proxy Config
# PROXY_HOST = "geo.iproyal.com"
# PROXY_PORT = 11202
# PROXY_USER = "16H4QGoZ0UmnaEB4"

# # CRITICAL: Static session ID so IPRoyal gives us the SAME IP 
# PROXY_SESSION_ID = "my_static_session_123" 
# BASE_PASS = "q1dYSNtI0heQXxRA_country-us_state-arizona_streaming-1"
# PROXY_PASS = f"{BASE_PASS}_session-{PROXY_SESSION_ID}"

# PROXY_CONFIG = {
#     "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
#     "username": PROXY_USER,
#     "password": PROXY_PASS,
# }

# # ─────────────────────────────────────────────────────────────────────────────
# # Phase 1: Manual Solve & Save
# # ─────────────────────────────────────────────────────────────────────────────
# async def manual_solve_and_save():
#     logging.info("Starting Phase 1: Manual Solving Mode")
    
#     async with AsyncCamoufox(
#         headless=False,
#         geoip=True,
#         proxy=PROXY_CONFIG,
#     ) as browser:
        
#         context = await browser.new_context(
#             viewport={"width": 1920, "height": 1080}
#         )
#         page = await context.new_page()
        
#         # --- NEW: Extract and save the exact User-Agent ---
#         user_agent = await page.evaluate("navigator.userAgent")
#         with open(UA_FILE, "w") as f:
#             f.write(user_agent)
#         logging.info(f"🔒 Locked Fingerprint (User-Agent): {user_agent}")
        
#         await page.goto(TARGET_URL)
#         logging.info("Waiting for you to pass the Cloudflare check...")
        
#         while True:
#             try:
#                 title = await page.title()
#                 if "Just a moment" not in title and "Cloudflare" not in title and "Attention Required" not in title:
#                     logging.info(f"✅ Success! Page transitioned to: '{title}'")
#                     break
#             except PlaywrightError as e:
#                 if "Execution context was destroyed" in str(e):
#                     logging.info("Navigation detected! Cloudflare is redirecting you...")
#                 else:
#                     pass
#             await asyncio.sleep(2)
            
#         logging.info("Waiting 5 seconds for cookies to settle...")
#         await asyncio.sleep(5)
        
#         await context.storage_state(path=SESSION_FILE)
#         logging.info(f"💾 Session successfully saved to {SESSION_FILE}")
        
#         await context.close()


# # ─────────────────────────────────────────────────────────────────────────────
# # Phase 2: Automated Scrape using Saved Session
# # ─────────────────────────────────────────────────────────────────────────────
# async def automated_scrape():
#     if not os.path.exists(SESSION_FILE) or not os.path.exists(UA_FILE):
#         logging.error("Session or User-Agent file not found. Run Phase 1 first!")
#         return

#     logging.info("Starting Phase 2: Automated Scraping Mode")
    
#     # --- NEW: Read the saved User-Agent ---
#     with open(UA_FILE, "r") as f:
#         saved_user_agent = f.read().strip()
    
#     async with AsyncCamoufox(
#         headless=False,  # CRITICAL: Cloudflare often blocks Headless=True even with a cookie.
#         geoip=True,
#         proxy=PROXY_CONFIG,
#     ) as browser:
        
#         # --- NEW: Inject both the cookie state AND the exact User-Agent ---
#         context = await browser.new_context(
#             viewport={"width": 1920, "height": 1080},
#             storage_state=SESSION_FILE,
#             user_agent=saved_user_agent
#         )
#         page = await context.new_page()
        
#         logging.info("Navigating to target URL using saved session...")
#         await page.goto(TARGET_URL)
        
#         await asyncio.sleep(3)
        
#         title = await page.title()
#         if "Just a moment" in title or "Cloudflare" in title:
#             logging.error("❌ Cloudflare rejected the session. IP might have changed or cookie expired.")
#         else:
#             logging.info(f"✅ Bypassed Cloudflare automatically! Current Title: '{title}'")
            
#             # --- Do your scraping here ---
#             # html = await page.content()
            
#         await context.close()


# # ─────────────────────────────────────────────────────────────────────────────
# # Menu
# # ─────────────────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     print("="*50)
#     print(" Cloudflare Session Manager ")
#     print("="*50)
#     print("1: Open browser to manually solve Captcha and save session")
#     print("2: Run automated scraper using saved session")
#     print("="*50)
    
#     choice = input("Enter 1 or 2: ").strip()
    
#     if choice == '1':
#         asyncio.run(manual_solve_and_save())
#     elif choice == '2':
#         asyncio.run(automated_scrape())
#     else:
#         print("Invalid choice. Exiting.")

import asyncio
import logging
import os
import random

from camoufox import AsyncCamoufox
from playwright.async_api import Error as PlaywrightError

logging.basicConfig(
    level='INFO',
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
# Put all 100 of your target URLs in this list
TARGET_URLS = [
    # "https://searchpeoplefree.com/find/saksham/mn/kandiyohi",
    # "https://searchpeoplefree.com/find/ruby/mn/kandiyohi",
    # "https://searchpeoplefree.com/find/alex/mn/kandiyohi",
    # "https://searchpeoplefree.com/find/saksham-kaushish",
    # "https://searchpeoplefree.com/find/another/person...",
    # add the rest here...
    
#   "https://searchpeoplefree.com/find/michael-smith/tx/harris",
#   "https://searchpeoplefree.com/find/jennifer-johnson/fl/miami-dade",
#   "https://searchpeoplefree.com/find/james-williams/ca/los-angeles",
#   "https://searchpeoplefree.com/find/emily-brown/ny/kings",
#   "https://searchpeoplefree.com/find/david-jones/il/cook",
#   "https://searchpeoplefree.com/find/sarah-garcia/az/maricopa",
#   "https://searchpeoplefree.com/find/christopher-miller/oh/franklin",
#   "https://searchpeoplefree.com/find/jessica-davis/ga/fulton",
#   "https://searchpeoplefree.com/find/matthew-rodriguez/nc/wake",
#   "https://searchpeoplefree.com/find/ashley-martinez/co/denver",
#   "https://searchpeoplefree.com/find/daniel-hernandez/wa/king",
#   "https://searchpeoplefree.com/find/amanda-lopez/nv/clark",
#   "https://searchpeoplefree.com/find/joshua-gonzalez/or/multnomah",
  "https://searchpeoplefree.com/find/megan-wilson/pa/allegheny",
  "https://searchpeoplefree.com/find/andrew-anderson/mi/wayne",
  "https://searchpeoplefree.com/find/nicole-thomas/tn/davidson",
  "https://searchpeoplefree.com/find/ryan-taylor/va/fairfax",
  "https://searchpeoplefree.com/find/lauren-moore/mo/st-louis",
  "https://searchpeoplefree.com/find/brandon-jackson/sc/greenville",
  "https://searchpeoplefree.com/find/rachel-martin/in/marion",
  "https://searchpeoplefree.com/find/kevin-lee/ma/middlesex",
  "https://searchpeoplefree.com/find/stephanie-perez/nj/bergen",
  "https://searchpeoplefree.com/find/justin-thompson/md/montgomery",
  "https://searchpeoplefree.com/find/brittany-white/ky/jefferson",
  "https://searchpeoplefree.com/find/tyler-harris/al/jefferson"

    
    
]

SESSION_FILE = "cloudflare_session.json"
UA_FILE = "user_agent.txt"

# Proxy Config
PROXY_HOST = "geo.iproyal.com"
PROXY_PORT = 11202
PROXY_USER = "16H4QGoZ0UmnaEB4"
PROXY_SESSION_ID = "my_static_session_123" 
PROXY_PASS = f"q1dYSNtI0heQXxRA_country-us_state-arizona_streaming-1_session-{PROXY_SESSION_ID}"

PROXY_CONFIG = {
    "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
    "username": PROXY_USER,
    "password": PROXY_PASS,
}

# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Manual Solve & Save (Run this once to get the clearance)
# ─────────────────────────────────────────────────────────────────────────────
async def manual_solve_and_save():
    logging.info("Starting Phase 1: Manual Solving Mode")
    
    async with AsyncCamoufox(
        headless=False,
        geoip=True,
        proxy=PROXY_CONFIG,
    ) as browser:
        
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        # Extract and save the exact User-Agent
        user_agent = await page.evaluate("navigator.userAgent")
        with open(UA_FILE, "w") as f:
            f.write(user_agent)
        logging.info(f"🔒 Locked Fingerprint (User-Agent): {user_agent}")
        
        await page.goto(TARGET_URLS[0])
        logging.info("Waiting for you to pass the Cloudflare check...")
        
        while True:
            try:
                title = await page.title()
                if "Just a moment" not in title and "Cloudflare" not in title and "Attention Required" not in title:
                    logging.info(f"✅ Success! Page transitioned to: '{title}'")
                    break
            except PlaywrightError as e:
                if "Execution context was destroyed" in str(e):
                    logging.info("Navigation detected! Cloudflare is redirecting you...")
            await asyncio.sleep(2)
            
        logging.info("Waiting 5 seconds for cookies to settle...")
        await asyncio.sleep(5)
        
        await context.storage_state(path=SESSION_FILE)
        logging.info(f"💾 Session successfully saved to {SESSION_FILE}")
        await context.close()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Scaled Automated Scrape (The 100-Entry Loop)
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Scaled Automated Scrape (The 100-Entry Loop)
# ─────────────────────────────────────────────────────────────────────────────
# async def automated_scrape_bulk():
#     if not os.path.exists(SESSION_FILE) or not os.path.exists(UA_FILE):
#         logging.error("Session or User-Agent file not found. Run Phase 1 first!")
#         return

#     logging.info(f"Starting Bulk Phase 2 with {len(TARGET_URLS)} search URLs.")
    
#     # Read the exact User-Agent from Phase 1
#     with open(UA_FILE, "r") as f:
#         saved_user_agent = f.read().strip()
    
#     async with AsyncCamoufox(
#         headless=False,  # Keep visible/minimized to stay highly trusted by Cloudflare
#         geoip=True,
#         proxy=PROXY_CONFIG,
#     ) as browser:
        
#         # Inject both the saved cookies AND the exact User-Agent
#         context = await browser.new_context(
#             viewport={"width": 1920, "height": 1080},
#             storage_state=SESSION_FILE,
#             user_agent=saved_user_agent
#         )
#         page = await context.new_page()
        
#         # ─── 1. LOOP THROUGH ALL SEARCH TARGETS ───
#         for index, search_url in enumerate(TARGET_URLS, start=1):
#             logging.info(f"[{index}/{len(TARGET_URLS)}] Processing Search URL: {search_url}")
            
#             try:
#                 await page.goto(search_url, wait_until="domcontentloaded")
#                 await asyncio.sleep(random.uniform(2.5, 4.0))
                
#                 title = await page.title()
                
#                 # Failsafe: Did Cloudflare revoke our session mid-loop?
#                 if "Just a moment" in title or "Cloudflare" in title:
#                     logging.error(f"❌ Session revoked at search entry #{index}! Cloudflare caught on. Exiting loop.")
#                     break
                    
#                 logging.info(f"✅ Search page loaded. Title: '{title}'")
                
#                 # ─── 2. EXTRACT "MORE FREE DETAILS" LINKS ───
#                 # Wait to ensure the profile cards are actually rendered in the DOM
#                 try:
#                     await page.wait_for_selector('a:has-text("More Free Details")', timeout=10000)
#                 except Exception:
#                     logging.warning(f"No 'More Free Details' buttons found on search {index}. Skipping.")
#                     continue
                
#                 # Evaluate JavaScript to grab all hrefs from the matching buttons
#                 detail_links = await page.locator('a:has-text("More Free Details")').evaluate_all(
#                     "elements => elements.map(el => el.href)"
#                 )
                
#                 detail_links = detail_links[:3]
                
#                 logging.info(f"Found {len(detail_links)} detail pages to scrape from this search result.")
                
#                 # ─── 3. LOOP THROUGH EACH DETAIL PAGE ───
#                 for detail_index, detail_url in enumerate(detail_links, start=1):
#                     logging.info(f"  -> Visiting detail page {detail_index}/{len(detail_links)}: {detail_url}")
                    
#                     # Navigate to the specific person's detail page
#                     await page.goto(detail_url, wait_until="domcontentloaded")
#                     await asyncio.sleep(random.uniform(2.5, 4.0))
                    
#                     detail_title = await page.title()
#                     if "Just a moment" in detail_title or "Cloudflare" in detail_title:
#                         logging.error(f"❌ Session revoked on detail page! Exiting.")
#                         return # Exit the entire function if Cloudflare blocks us here
                        
#                     # --- ADD YOUR SPECIFIC DETAIL PAGE EXTRACTION LOGIC HERE ---
#                     # Example: Get the HTML and save it, or extract specific locators
#                     # html = await page.content()
#                     # with open(f"person_{index}_{detail_index}.html", "w", encoding="utf-8") as f:
#                     #     f.write(html)
#                     # -----------------------------------------------------------
                    
#                     # CRITICAL: Human-like pacing between visiting individual detail pages
#                     if detail_index < len(detail_links):
#                         cooldown = random.uniform(4.0, 7.0)
#                         logging.info(f"  -> Sleeping {cooldown:.2f}s before next detail page...")
#                         await asyncio.sleep(cooldown)

#             except Exception as e:
#                 logging.error(f"Failed to process search entry #{index}: {e}")
            
#             # CRITICAL: Human-like pacing between main search URLs
#             if index < len(TARGET_URLS):
#                 cooldown = random.uniform(5.5, 9.5)
#                 logging.info(f"Sleeping for {cooldown:.2f}s before next main search URL...")
#                 await asyncio.sleep(cooldown)
            
#         await context.close()
    
#     logging.info("Bulk processing completed.")



# //new scrapebulk
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Scaled Automated Scrape (The Top-3 Bulk Loop)
# ─────────────────────────────────────────────────────────────────────────────
async def automated_scrape_bulk():
    if not os.path.exists(SESSION_FILE) or not os.path.exists(UA_FILE):
        logging.error("Session or User-Agent file not found. Run Phase 1 first!")
        return

    logging.info(f"Starting Bulk Phase 2 with {len(TARGET_URLS)} search URLs.")
    
    # Read the exact User-Agent from Phase 1
    with open(UA_FILE, "r") as f:
        saved_user_agent = f.read().strip()
    
    async with AsyncCamoufox(
        headless=False,  # Keep visible/minimized to stay highly trusted by Cloudflare
        geoip=True,
        proxy=PROXY_CONFIG,
    ) as browser:
        
        # Inject both the saved cookies AND the exact User-Agent
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            storage_state=SESSION_FILE,
            user_agent=saved_user_agent
        )
        page = await context.new_page()
        
        # ─── 1. LOOP THROUGH ALL SEARCH TARGETS ───
        for index, search_url in enumerate(TARGET_URLS, start=1):
            logging.info(f"[{index}/{len(TARGET_URLS)}] Processing Search URL: {search_url}")
            
            try:
                await page.goto(search_url, wait_until="domcontentloaded")
                await asyncio.sleep(random.uniform(2.5, 4.0))
                
                title = await page.title()
                
                # Failsafe: Did Cloudflare revoke our session mid-loop?
                if "Just a moment" in title or "Cloudflare" in title:
                    logging.error(f"❌ Session revoked at search entry #{index}! Cloudflare caught on. Exiting loop.")
                    break
                    
                logging.info(f"✅ Search page loaded. Title: '{title}'")
                
                # ─── 2. EXTRACT "MORE FREE DETAILS" LINKS (TOP 3 ONLY) ───
                try:
                    await page.wait_for_selector('a:has-text("More Free Details")', timeout=10000)
                except Exception:
                    logging.warning(f"No 'More Free Details' buttons found on search {index}. Skipping.")
                    continue
                
                # Evaluate JavaScript to grab all hrefs from the matching buttons
                detail_links = await page.locator('a:has-text("More Free Details")').evaluate_all(
                    "elements => elements.map(el => el.href)"
                )
                
                # Limit to the top 3 results to save time/bandwidth
                detail_links = detail_links[:3]
                
                logging.info(f"Found {len(detail_links)} top detail pages to scrape from this search result.")
                
                # ─── 3. LOOP THROUGH EACH DETAIL PAGE ───
                for detail_index, detail_url in enumerate(detail_links, start=1):
                    logging.info(f"  -> Visiting detail page {detail_index}/{len(detail_links)}: {detail_url}")
                    
                    await page.goto(detail_url, wait_until="domcontentloaded")
                    await asyncio.sleep(random.uniform(2.5, 4.0))
                    
                    detail_title = await page.title()
                    if "Just a moment" in detail_title or "Cloudflare" in detail_title:
                        logging.error(f"❌ Session revoked on detail page! Exiting entire process.")
                        return 
                        
                    # ─── 4. EXTRACTION LOGIC ───
                    person_data = {
                        "search_term": search_url,
                        "profile_url": detail_url,
                        "name": None,
                        "age": None,
                        "raw_current_info": None,
                        "phone_numbers": [],
                        "previous_addresses": [],
                        "aliases": [],
                        "relatives": [],
                        "associates": []
                    }

                    # Inline helper function for resilient DOM extraction
                    async def safe_extract(selector, all_elements=False, parent_selector=None):
                        try:
                            base = page.locator(parent_selector) if parent_selector else page
                            target = base.locator(selector)
                            
                            if all_elements:
                                elements = await target.all_inner_texts()
                                return [text.strip() for text in elements if text.strip()]
                            else:
                                text = await target.first.inner_text(timeout=2000)
                                return text.strip()
                        except Exception:
                            return [] if all_elements else None

                    # Extract data using the semantic HTML classes
                    person_data["name"] = await safe_extract('h1')
                    person_data["age"] = await safe_extract('text=/^Age \\d+/i', parent_selector='article.current-bg')
                    person_data["raw_current_info"] = await safe_extract('article.current-bg')
                    
                    phones = await safe_extract('a', all_elements=True, parent_selector='article.phone-bg')
                    person_data["phone_numbers"] = [p for p in phones if any(char.isdigit() for char in p)]
                    
                    person_data["previous_addresses"] = await safe_extract('a', all_elements=True, parent_selector='article.address-bg')
                    person_data["aliases"] = await safe_extract('a', all_elements=True, parent_selector='article.alias-bg')
                    person_data["relatives"] = await safe_extract('a', all_elements=True, parent_selector='article.family-bg')
                    person_data["associates"] = await safe_extract('a', all_elements=True, parent_selector='article.associate-bg')

                    # ─── 5. SAVE DATA IMMEDIATELY TO JSONL ───
                    import json
                    with open("people_result.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps(person_data) + "\n")
                        
                    logging.info(f"  -> Successfully saved data for: {person_data['name']}")
                    
                    # Human-like pacing between visiting individual detail pages
                    if detail_index < len(detail_links):
                        cooldown = random.uniform(4.0, 7.0)
                        logging.info(f"  -> Sleeping {cooldown:.2f}s before next detail page...")
                        await asyncio.sleep(cooldown)

            except Exception as e:
                logging.error(f"Failed to process search entry #{index}: {e}")
            
            # Human-like pacing between main search URLs
            if index < len(TARGET_URLS):
                cooldown = random.uniform(5.5, 9.5)
                logging.info(f"Sleeping for {cooldown:.2f}s before next main search URL...")
                await asyncio.sleep(cooldown)
            
        await context.close()
    
    logging.info("Bulk processing completed.")
# ─────────────────────────────────────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*50)
    print(" Cloudflare Session Manager & Bulk Scraper ")
    print("="*50)
    print("1: Open browser to manually solve Captcha and save session (Phase 1)")
    print("2: Run bulk automated scraper using saved session (Phase 2)")
    print("="*50)
    
    choice = input("Enter 1 or 2: ").strip()
    
    if choice == '1':
        asyncio.run(manual_solve_and_save())
    elif choice == '2':
        asyncio.run(automated_scrape_bulk())
    else:
        print("Invalid choice. Exiting.")