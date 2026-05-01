

# import asyncio
# import logging
# import re
# import json
# from bs4 import BeautifulSoup
# from patchright.async_api import async_playwright  # only change vs standard playwright
# from playwright_captcha import CaptchaType, ClickSolver, FrameworkType

# logging.basicConfig(
#     level='INFO',
#     format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )

# QUERY = "nurse"
# OUTPUT_FILE = "iuhealth_jobs.json"


# def get_url(page_num: int, query: str) -> str:
#     if page_num == 1:
#         return f"https://careers.iuhealth.org/search/jobs?q={query}"
#     return f"https://careers.iuhealth.org/search/jobs/in?page={page_num}&q={query}"


# async def handle_captcha_if_needed(page, solver: ClickSolver) -> bool:
#     captcha_indicators = [
#         "iframe[src*='challenges.cloudflare.com']",
#         "#challenge-form",
#         ".cf-challenge-running",
#         "#cf-challenge-running",
#         "iframe[src*='hcaptcha.com']",
#         "iframe[src*='recaptcha']",
#     ]

#     # ✅ FIXED — explicit async loop instead of generator in any()
#     detected = False
#     for sel in captcha_indicators:
#         try:
#             if await page.query_selector(sel):
#                 detected = True
#                 break
#         except Exception:
#             continue

#     if detected:
#         logging.info("⚠️  Cloudflare challenge detected. Attempting auto-solve...")
#         try:
#             await solver.solve_captcha(
#                 captcha_container=page,
#                 captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
#                 expected_content_selector=".jobs-section__item"
#             )
#             await asyncio.sleep(3)
#             logging.info("✅ Captcha solved.")
#             return True
#         except Exception as e:
#             logging.error(f"❌ Auto-solve failed: {e}. Waiting for manual solve (120s)...")
#             try:
#                 await page.wait_for_selector(".jobs-section__item", timeout=120_000)
#                 logging.info("✅ Manual solve detected.")
#                 return True
#             except Exception as e2:
#                 logging.error(f"Manual solve timeout: {e2}")
#                 return False
#     return False

# async def scrape_page(page, solver: ClickSolver, url: str):
#     await page.goto(url, timeout=60_000)
#     await asyncio.sleep(3)
#     await handle_captcha_if_needed(page, solver)

#     try:
#         await page.wait_for_selector(".jobs-section__item", timeout=30_000)
#     except Exception:
#         logging.warning("Jobs not found — rechecking for captcha...")
#         await handle_captcha_if_needed(page, solver)
#         await page.wait_for_selector(".jobs-section__item", timeout=30_000)

#     soup = BeautifulSoup(await page.content(), "lxml")
#     rows = soup.select(".jobs-section__item")

#     jobs = []
#     for row in rows:
#         cols = row.select(".columns")
#         link_tag = cols[0].find("a") if cols else None
#         href = link_tag["href"] if link_tag else ""
#         jobs.append({
#             "title":       cols[0].get_text(strip=True) if len(cols) > 0 else "",
#             "facility":    re.sub(r"Facility:", "", cols[1].get_text(strip=True)) if len(cols) > 1 else "",
#             "location":    re.sub(r'\s+', ' ', cols[2].get_text(strip=True)).replace("Location:", "") if len(cols) > 2 else "",
#             "date_posted": re.sub(r"Date Posted:", "", cols[3].get_text(strip=True)) if len(cols) > 3 else "",
#             "url":         ("https://careers.iuhealth.org" + href) if href.startswith("/") else href,
#         })

#     has_next = soup.select_one("a.next_page") is not None
#     return jobs, has_next


# async def main():
#     all_jobs = []

#     # Patchright launches real Chrome (channel="chrome") with patches applied
#     async with async_playwright() as playwright:
#         browser = await playwright.chromium.launch(
#             channel="chrome",       # uses your installed Chrome — more human-like fingerprint
#             headless=False,         # set True once you confirm captchas are auto-solved
#         )
#         context = await browser.new_context(
#             user_agent=(
#                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                 "AppleWebKit/537.36 (KHTML, like Gecko) "
#                 "Chrome/124.0.0.0 Safari/537.36"
#             )
#         )
#         page = await context.new_page()

#         async with ClickSolver(framework=FrameworkType.PATCHRIGHT, page=page) as solver:
#             current_page = 1
#             while True:
#                 url = get_url(current_page, QUERY)
#                 logging.info(f"Scraping page {current_page}: {url}")
#                 try:
#                     jobs, has_next = await scrape_page(page, solver, url)
#                     all_jobs.extend(jobs)
#                     logging.info(f"✅ Got {len(jobs)} jobs. Total: {len(all_jobs)}")
#                 except Exception as e:
#                     logging.error(f"❌ Failed on page {current_page}: {e}")
#                     logging.info("Waiting 15s before retry...")
#                     await asyncio.sleep(15)
#                     continue

#                 if not has_next:
#                     logging.info("No next page. Done.")
#                     break

#                 current_page += 1
#                 await asyncio.sleep(1.5)

#         await browser.close()

#     with open(OUTPUT_FILE, "w") as f:
#         json.dump(all_jobs, f, indent=2)
#     logging.info(f"✅ Saved {len(all_jobs)} jobs to {OUTPUT_FILE}")


# if __name__ == "__main__":
#     asyncio.run(main())



import asyncio
import logging
import re
import json
from bs4 import BeautifulSoup
from patchright.async_api import async_playwright
from playwright_captcha import CaptchaType, ClickSolver, FrameworkType

logging.basicConfig(
    level='INFO',
    format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

QUERY = "nurse"
OUTPUT_FILE = "iuhealth_jobs.json"
MAX_CONCURRENT_DETAIL_PAGES = 3   # how many job detail pages to fetch in parallel
HEADLESS = True                    # ← toggle this to switch headless on/off


def get_url(page_num: int, query: str) -> str:
    if page_num == 1:
        return f"https://careers.iuhealth.org/search/jobs?q={query}"
    return f"https://careers.iuhealth.org/search/jobs/in?page={page_num}&q={query}"


async def handle_captcha_if_needed(page, solver: ClickSolver) -> bool:
    captcha_indicators = [
        "iframe[src*='challenges.cloudflare.com']",
        "#challenge-form",
        ".cf-challenge-running",
        "#cf-challenge-running",
        "iframe[src*='hcaptcha.com']",
        "iframe[src*='recaptcha']",
    ]

    detected = False
    for sel in captcha_indicators:
        try:
            if await page.query_selector(sel):
                detected = True
                break
        except Exception:
            continue

    if detected:
        logging.info("⚠️  Cloudflare challenge detected. Attempting auto-solve...")
        try:
            await solver.solve_captcha(
                captcha_container=page,
                captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                expected_content_selector=".jobs-section__item"
            )
            await asyncio.sleep(3)
            logging.info("✅ Captcha solved.")
            return True
        except Exception as e:
            logging.error(f"❌ Auto-solve failed: {e}")
            if not HEADLESS:
                logging.info("Waiting for manual solve (120s)...")
                try:
                    await page.wait_for_selector(".jobs-section__item", timeout=120_000)
                    logging.info("✅ Manual solve detected.")
                    return True
                except Exception as e2:
                    logging.error(f"Manual solve timeout: {e2}")
            return False
    return False


async def scrape_listing_page(page, solver: ClickSolver, url: str):
    """Scrape a single listing page — returns list of basic job dicts + has_next."""
    await page.goto(url, timeout=60_000)
    await asyncio.sleep(3)
    await handle_captcha_if_needed(page, solver)

    try:
        await page.wait_for_selector(".jobs-section__item", timeout=30_000)
    except Exception:
        logging.warning("Jobs not found — rechecking for captcha...")
        await handle_captcha_if_needed(page, solver)
        await page.wait_for_selector(".jobs-section__item", timeout=30_000)

    soup = BeautifulSoup(await page.content(), "lxml")
    rows = soup.select(".jobs-section__item")

    jobs = []
    for row in rows:
        cols = row.select(".columns")
        link_tag = cols[0].find("a") if cols else None
        href = link_tag["href"] if link_tag else ""
        jobs.append({
            "title":       cols[0].get_text(strip=True) if len(cols) > 0 else "",
            "facility":    re.sub(r"Facility:", "", cols[1].get_text(strip=True)) if len(cols) > 1 else "",
            "location":    re.sub(r'\s+', ' ', cols[2].get_text(strip=True)).replace("Location:", "") if len(cols) > 2 else "",
            "date_posted": re.sub(r"Date Posted:", "", cols[3].get_text(strip=True)) if len(cols) > 3 else "",
            "url":         ("https://careers.iuhealth.org" + href) if href.startswith("/") else href,
            "description": None,   # filled in later
        })

    has_next = soup.select_one("a.next_page") is not None
    return jobs, has_next


async def fetch_job_description(context, solver: ClickSolver, job: dict, semaphore: asyncio.Semaphore) -> dict:
    """
    Open a new browser tab, navigate to the job detail page,
    handle any captcha, extract the description, then close the tab.
    """
    async with semaphore:   # limits concurrent tabs to MAX_CONCURRENT_DETAIL_PAGES
        page = await context.new_page()
        try:
            logging.info(f"  Fetching description: {job['title'][:50]}...")
            await page.goto(job["url"], timeout=60_000)
            await asyncio.sleep(2)

            # Handle captcha on detail page too
            detected = False
            for sel in [
                "iframe[src*='challenges.cloudflare.com']",
                "#challenge-form", ".cf-challenge-running",
            ]:
                if await page.query_selector(sel):
                    detected = True
                    break

            if detected:
                try:
                    await solver.solve_captcha(
                        captcha_container=page,
                        captcha_type=CaptchaType.CLOUDFLARE_INTERSTITIAL,
                        expected_content_selector=".job-description"  # adjust if needed
                    )
                    await asyncio.sleep(3)
                except Exception as e:
                    logging.warning(f"  Captcha on detail page failed: {e}")

            # Wait for description container — try multiple common selectors
            description_selectors = [
                ".job-description",
                ".description",
                "[data-bind*='description']",
                ".ats-description",
                "#job-description",
                ".job-details",
                "article",
                "page-section-large",
                ".job-details__main"
            ]

            description_text = ""
            description_text = ""
            for sel in description_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=8_000)
                    el = await page.query_selector(sel)
                    if el:
                        # Grab text cleanly from the nested structure
                        description_text = await el.evaluate('''container => {
                            const elements = container.querySelectorAll('h2, p, li');
                            let extractedText = [];
                            
                            elements.forEach(el => {
                                // innerText handles nested tags like <b> automatically
                                const text = el.innerText.trim(); 
                                if (text) {
                                    if (el.tagName.toLowerCase() === 'li') {
                                        extractedText.push('- ' + text);
                                    } else {
                                        extractedText.push(text);
                                    }
                                }
                            });
                            
                            return extractedText.join('\\n\\n');
                        }''')
                        
                        # Clean up any leftover double spacing
                        description_text = re.sub(r'\n{3,}', '\n\n', description_text).strip()
                        break
                except Exception:
                    continue
                try:
                    await page.wait_for_selector(sel, timeout=8_000)
                    el = await page.query_selector(sel)
                    if el:
                        # Use JavaScript to pull specific tags in document order
                        description_text = await el.evaluate('''container => {
                            // Select only the tags you care about inside the container
                            const elements = container.querySelectorAll('h2, p, li');
                            let extractedText = [];
                            
                            elements.forEach(el => {
                                const text = el.innerText.trim();
                                if (text) {
                                    // Add a dash to list items so they look nice
                                    if (el.tagName.toLowerCase() === 'li') {
                                        extractedText.push('- ' + text);
                                    } else {
                                        extractedText.push(text);
                                    }
                                }
                            });
                            
                            // Join everything with double newlines for readability
                            return extractedText.join('\\n\\n');
                        }''')
                        
                        # Clean up any excessive newlines just in case
                        description_text = re.sub(r'\n{3,}', '\n\n', description_text).strip()
                        break
                except Exception:
                    continue

            if not description_text:
                logging.warning(f"  ⚠️  No description found for: {job['title'][:50]}")

            job["description"] = description_text
        except Exception as e:
            logging.error(f"  ❌ Failed to fetch description for {job['url']}: {e}")
            job["description"] = ""
        finally:
            await page.close()

        return job


async def main():
    all_jobs = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=HEADLESS,
            # These args improve headless stealth
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ] if HEADLESS else ["--start-maximized"],
        )
        context = await browser.new_context(
            # Realistic viewport even in headless mode
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        # Main listing page (used for pagination)
        listing_page = await context.new_page()

        # Semaphore to cap parallel detail-page tabs
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DETAIL_PAGES)

        async with ClickSolver(framework=FrameworkType.PATCHRIGHT, page=listing_page) as solver:

            # ── Phase 1: Collect all job stubs from listing pages ──────────────
            current_page = 1
            while current_page<2:
                url = get_url(current_page, QUERY)
                logging.info(f"Scraping listing page {current_page}: {url}")
                try:
                    jobs, has_next = await scrape_listing_page(listing_page, solver, url)
                    all_jobs.extend(jobs)
                    logging.info(f"  ✅ Got {len(jobs)} jobs. Total so far: {len(all_jobs)}")
                except Exception as e:
                    logging.error(f"  ❌ Failed on listing page {current_page}: {e}")
                    logging.info("  Waiting 15s before retry...")
                    await asyncio.sleep(15)
                    continue

                if not has_next:
                    logging.info("No next listing page. Moving to detail scrape.")
                    break

                current_page += 1
                await asyncio.sleep(1.5)

            # ── Phase 2: Fetch descriptions in parallel ────────────────────────
            logging.info(f"\nFetching descriptions for {len(all_jobs)} jobs "
                         f"({MAX_CONCURRENT_DETAIL_PAGES} at a time)...")

            tasks = [
                fetch_job_description(context, solver, job, semaphore)
                for job in all_jobs
            ]
            all_jobs = await asyncio.gather(*tasks)

        await browser.close()

    with open(OUTPUT_FILE, "w") as f:
        json.dump(list(all_jobs), f, indent=2)

    logging.info(f"\n✅ Saved {len(all_jobs)} jobs with descriptions to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())