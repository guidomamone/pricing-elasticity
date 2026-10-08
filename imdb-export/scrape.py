import csv, re, sys, random
from playwright.sync_api import sync_playwright

USER_ID = input("Paste your IMDb user ID: ").strip()
MAX_PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 10**6
URL = f"https://www.imdb.com/user/{USER_ID}/ratings/"
ITEM = "li.ipc-metadata-list-summary-item"

CLICK_NEXT = """() => {
    const el = [...document.querySelectorAll('button,a,[role=button]')]
        .find(e => e.innerText.trim() === 'Next');
    if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
    el.scrollIntoView(); el.click(); return true;
}"""
GET_ROWS = """(sel) => [...document.querySelectorAll(sel)].map(li => {
    const a = li.querySelector('a[href*="/title/tt"]');
    return {href: a ? a.getAttribute('href') : '', text: li.innerText};
})"""

def first_text(page):
    loc = page.locator(ITEM)
    return loc.first.inner_text()[:80] if loc.count() else ""

seen = set()
total = 0
with open("ratings_raw.csv", "w", newline="", encoding="utf-8") as f, sync_playwright() as p:
    w = csv.writer(f)
    w.writerow(["const", "title", "your_rating", "date_rated", "raw_text"])

    ctx = p.chromium.launch_persistent_context("./profile", headless=False)
    page = ctx.new_page()
    page.goto(URL)
    input("Wait until your ratings list is showing, then press Enter here (just Enter, type nothing)... ")

    pg = 0
    while pg < MAX_PAGES:
        pg += 1
        page.wait_for_selector(ITEM)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        before = first_text(page)

        new = 0
        for r in page.evaluate(GET_ROWS, ITEM):
            m = re.search(r"tt\d+", r["href"])
            const = m.group(0) if m else ""
            if const and const in seen:
                continue
            seen.add(const)
            parts = [x.strip() for x in r["text"].split("\n")]
            txt = " | ".join(parts)
            t = next((re.sub(r"^\d+\.\s*", "", x) for x in parts if re.match(r"^\d+\.\s", x)), "")
            d = re.search(r"Rated on ([^|]+)", txt)
            nums = [x for x in parts if re.fullmatch(r"(10|[1-9])", x)]
            w.writerow([const, t, nums[-1] if nums else "", d.group(1).strip() if d else "", txt])
            new += 1
        f.flush()
        total += new
        print(f"page {pg}: +{new} new, {total} total")

        if not page.evaluate(CLICK_NEXT):
            print("No Next button left, that's the end.")
            break
        for _ in range(40):
            page.wait_for_timeout(500)
            if first_text(page) != before:
                break
        else:
            print("Page did not change after clicking Next, stopping.")
            break
        page.wait_for_timeout(random.randint(1500, 3500))
    ctx.close()

print(f"Done. {total} rows in ratings_raw.csv")
