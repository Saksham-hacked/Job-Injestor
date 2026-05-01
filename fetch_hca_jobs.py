#!/usr/bin/env python3
"""
Fetch HCA jobs from Darwinbox using Playwright browser context
to bypass Cloudflare 403 on raw requests.

Run:
    python fetch_hca_jobs_playwright.py

Optional:
    python fetch_hca_jobs_playwright.py --save-json hca_jobs.json
    python fetch_hca_jobs_playwright.py --save-csv hca_jobs.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from html import unescape
from typing import Any

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------

BASE_URL = "https://hcahr.darwinbox.in"
CAREERS_URL = f"{BASE_URL}/ms/candidatev2/main/careers/allJobs"
API_URL = f"{BASE_URL}/ms/candidateapi/job/alljobs?companyId=main"

DEFAULT_LIMIT = 10
PAGE_LOAD_WAIT_MS = 5000
BETWEEN_PAGES_WAIT_MS = 600


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def make_payload(page: int, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    return {
        "companyId": "main",
        "page": page,
        "sort_option": "new",
        "limit": limit,
    }


def html_to_text(html: str) -> str:
    if not html:
        return ""

    text = unescape(html)

    # Replace common block tags with newlines
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)

    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Normalize whitespace
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)

    return text.strip()


def normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    title = (
        job.get("title")
        or job.get("designation_display_name")
        or job.get("designation_name")
        or ""
    ).strip()

    department = (
        job.get("department_name")
        or job.get("department_name_only")
        or ""
    ).strip()

    location = ""
    if job.get("officelocation_show_arr_list"):
        if isinstance(job["officelocation_show_arr_list"], list):
            location = ", ".join(str(x).strip() for x in job["officelocation_show_arr_list"] if x)
    elif job.get("officelocation_show_arr"):
        location = str(job["officelocation_show_arr"]).replace("\r", " ").replace("\n", " ").strip()
    elif job.get("locations"):
        location = str(job["locations"]).strip()

    description_html = str(job.get("jd") or "")
    description_text = html_to_text(description_html)

    job_id = str(job.get("id") or job.get("_id") or "")

    return {
        "job_id": job_id,
        "title": title,
        "department": department,
        "location": location,
        "country": str(job.get("country") or "").strip(),
        "employment_type": str(job.get("emp_type_name") or "").strip(),
        "posted_on": str(job.get("posted_on") or "").strip(),
        "apply_url": f"{CAREERS_URL}#job-{job_id}" if job_id else CAREERS_URL,
        "description_html": description_html,
        "description_text": description_text,
        "source_platform": "darwinbox",
        "source_url": API_URL,
        "raw": job,
    }


def save_json(path: str, jobs: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Saved JSON -> {path}")


def save_csv(path: str, jobs: list[dict[str, Any]]) -> None:
    fieldnames = [
        "job_id",
        "title",
        "department",
        "location",
        "country",
        "employment_type",
        "posted_on",
        "apply_url",
        "description_text",
        "source_platform",
        "source_url",
    ]

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for job in jobs:
            writer.writerow({
                "job_id": job["job_id"],
                "title": job["title"],
                "department": job["department"],
                "location": job["location"],
                "country": job["country"],
                "employment_type": job["employment_type"],
                "posted_on": job["posted_on"],
                "apply_url": job["apply_url"],
                "description_text": job["description_text"],
                "source_platform": job["source_platform"],
                "source_url": job["source_url"],
            })

    print(f"[INFO] Saved CSV -> {path}")


# ------------------------------------------------------------------------------
# Core Playwright Fetch
# ------------------------------------------------------------------------------

def browser_fetch_jobs_page(page, page_num: int, limit: int) -> list[dict[str, Any]]:
    payload = make_payload(page=page_num, limit=limit)

    js = """
    async ({ apiUrl, payload }) => {
        const resp = await fetch(apiUrl, {
            method: "POST",
            headers: {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json"
            },
            body: JSON.stringify(payload),
            credentials: "include"
        });

        const contentType = resp.headers.get("content-type") || "";
        const text = await resp.text();

        return {
            ok: resp.ok,
            status: resp.status,
            contentType,
            text
        };
    }
    """

    result = page.evaluate(js, {"apiUrl": API_URL, "payload": payload})

    if not result["ok"]:
        raise RuntimeError(
            f"Browser fetch failed: status={result['status']} "
            f"body={result['text'][:500]}"
        )

    if "json" not in result["contentType"].lower():
        raise RuntimeError(
            f"Unexpected content type from browser fetch: {result['contentType']} "
            f"body={result['text'][:500]}"
        )

    data = json.loads(result["text"])

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "jobs", "results", "openings", "positions"):
            if isinstance(data.get(key), list):
                return data[key]

    raise RuntimeError(f"Unexpected response shape: {type(data).__name__}")


def fetch_all_jobs_via_playwright(limit: int = DEFAULT_LIMIT, headless: bool = True) -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        page = context.new_page()

        print(f"[INFO] Opening careers page: {CAREERS_URL}")
        page.goto(CAREERS_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(PAGE_LOAD_WAIT_MS)

        # Optional: click Open Jobs / We Have X Open Jobs if visible
        click_selectors = [
            "text=Open Jobs",
            "button:has-text('Open Jobs')",
            "a:has-text('Open Jobs')",
            "text=We Have",
            "button:has-text('We Have')",
            "a:has-text('We Have')",
        ]

        for sel in click_selectors:
            try:
                locator = page.locator(sel).first
                if locator.count() > 0 and locator.is_visible():
                    locator.scroll_into_view_if_needed()
                    locator.click(timeout=4000)
                    print(f"[INFO] Clicked: {sel}")
                    page.wait_for_timeout(2500)
                    break
            except Exception:
                pass

        page_num = 1

        while True:
            jobs = browser_fetch_jobs_page(page, page_num=page_num, limit=limit)

            if not jobs:
                print(f"[INFO] No jobs on page {page_num}. Stopping.")
                break

            added = 0
            for job in jobs:
                job_id = str(job.get("id") or job.get("_id") or "")
                if job_id:
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                all_jobs.append(job)
                added += 1

            print(f"[INFO] Page {page_num}: fetched={len(jobs)} added={added} total={len(all_jobs)}")

            if len(jobs) < limit:
                print(f"[INFO] Last page detected (page {page_num})")
                break

            page_num += 1
            page.wait_for_timeout(BETWEEN_PAGES_WAIT_MS)

        browser.close()

    return all_jobs


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="Jobs per page (default: 10)")
    parser.add_argument("--save-json", type=str, default="", help="Save normalized jobs to JSON")
    parser.add_argument("--save-csv", type=str, default="", help="Save normalized jobs to CSV")
    parser.add_argument("--headed", action="store_true", help="Run browser in visible mode")
    args = parser.parse_args()

    try:
        raw_jobs = fetch_all_jobs_via_playwright(
            limit=args.limit,
            headless=not args.headed
        )
        normalized_jobs = [normalize_job(job) for job in raw_jobs]

        print("\n" + "=" * 80)
        print("HCA DARWINBOX JOBS (PLAYWRIGHT)")
        print("=" * 80)
        print(f"Total jobs fetched: {len(normalized_jobs)}")
        print("=" * 80)

        for i, job in enumerate(normalized_jobs[:10], start=1):
            print(f"{i:02d}. {job['title']} | {job['location']} | {job['posted_on']}")

        if len(normalized_jobs) > 10:
            print(f"... and {len(normalized_jobs) - 10} more")

        if args.save_json:
            save_json(args.save_json, normalized_jobs)

        if args.save_csv:
            save_csv(args.save_csv, normalized_jobs)

    except PlaywrightTimeoutError as e:
        print(f"[ERROR] Playwright timeout: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()