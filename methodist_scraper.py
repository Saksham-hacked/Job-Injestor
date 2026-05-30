


# import asyncio
# import random
# import json
# from patchright.async_api import async_playwright

# async def wait_for_text_change(frame, selector, old_text):
#     """Polls until the text at selector no longer matches old_text."""
#     timeout = 15
#     start_time = asyncio.get_event_loop().time()
#     while (asyncio.get_event_loop().time() - start_time) < timeout:
#         element = await frame.query_selector(selector)
#         if element:
#             current_text = await element.inner_text()
#             if current_text.strip() != old_text.strip():
#                 return True
#         await asyncio.sleep(0.5)
#     return False

# async def scrape_methodist():
#     all_jobs = []
    
#     async with async_playwright() as p:
#         # Using persistent context to keep your 'human' session tokens
#         user_data_dir = "./icims_session"
#         browser = await p.chromium.launch_persistent_context(
#             user_data_dir,
#             headless=True,
#             args=["--disable-blink-features=AutomationControlled"]
#         )

#         page = browser.pages[0]
#         print("Landing on search...")
#         await page.goto("https://careers-methodisthospitals.icims.com/jobs/search?ss=1", wait_until="networkidle")

#         try:
#             while True:
#                 # 1. Re-locate the frame on every loop iteration
#                 print(f"Accessing iframe (Jobs so far: {len(all_jobs)})...")
#                 await page.wait_for_selector("#icims_content_iframe", timeout=30000)
#                 iframe_handle = await page.query_selector("#icims_content_iframe")
#                 frame = await iframe_handle.content_frame()
                
#                 # 2. Wait for cards to render
#                 await frame.wait_for_selector(".iCIMS_JobCardItem", timeout=20000)
                
#                 # Capture current state
#                 first_job_elem = await frame.query_selector(".iCIMS_JobCardItem h3")
#                 first_job_before = await first_job_elem.inner_text()

#                 # 3. Extract current page jobs
#                 job_elements = await frame.query_selector_all(".iCIMS_JobCardItem")
#                 print(f"Scraped {len(job_elements)} jobs.")

#                 for element in job_elements:
#                     title_elem = await element.query_selector("h3")
#                     link_elem = await element.query_selector("a.iCIMS_Anchor")
#                     if title_elem and link_elem:
#                         all_jobs.append({
#                             "Title": (await title_elem.inner_text()).strip(),
#                             "URL": await link_elem.get_attribute("href")
#                         })

#                 # 4. Pagination
#                 await frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#                 await asyncio.sleep(1)

#                 next_btn = await frame.query_selector("a:has(.halflings-menu-right)")

#                 if next_btn:
#                     is_invisible = await next_btn.evaluate("node => node.classList.contains('invisible')")
                    
#                     if not is_invisible:
#                         print("Clicking Next...")
#                         await next_btn.evaluate("node => node.click()")
                        
#                         # 5. WAIT FOR CONTEXT RESET
#                         # Instead of checking text change immediately, we wait for the 
#                         # iframe to either reload or change content.
#                         print("Waiting for page update...")
#                         await asyncio.sleep(5) 
                        
#                         # We don't use 'wait_for_text_change' here because the 
#                         # next loop iteration will re-locate the frame anyway.
#                         continue 
#                     else:
#                         print("Reached final page.")
#                         break
#                 else:
#                     break
#         except Exception as e:
#             print(f"Error: {e}")

#         finally:
#             with open("methodist_jobs.json", "w", encoding="utf-8") as f:
#                 json.dump(all_jobs, f, indent=2, ensure_ascii=False)
#             print(f"\nScrape Finished. Total jobs saved: {len(all_jobs)}")
#             await browser.close()

# if __name__ == "__main__":
#     asyncio.run(scrape_methodist())


import asyncio
from patchright.async_api import async_playwright

async def diagnostic_scrape(url):
    async with async_playwright() as p:
        # We start FRESH - no session folder for this specific test
        # To see if the session is actually what's causing the block
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        if "in_iframe=1" not in url:
            url += "&in_iframe=1"

        print(f"Direct Navigation to: {url}")
        
        try:
            # We use 'commit' to catch the very first response from the server
            response = await page.goto(url, wait_until="commit", timeout=60000)
            print(f"Server Response Status: {response.status}")
            
            # Wait for 10 seconds to see if anything renders at all
            await asyncio.sleep(10)
            
            content = await page.content()
            body_text = await page.evaluate("document.body.innerText")
            
            print(f"Body Text Length: {len(body_text)}")
            print(f"Body Text Preview: {body_text[:200]}")
            
            with open("diagnostic_output.html", "w", encoding="utf-8") as f:
                f.write(content)
            
            print("Full HTML dumped to diagnostic_output.html")

        except Exception as e:
            print(f"Diagnostic Failed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    TEST_URL = "https://careers-methodisthospitals.icims.com/jobs/13198/medical-assistant-mpg-drk7055/job?in_iframe=1"
    asyncio.run(diagnostic_scrape(TEST_URL))