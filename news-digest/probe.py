#!/usr/bin/env python3
"""Probe candidate feeds: entry count, newest date, typical snippet length. Dev tool, not part of the digest."""
import statistics
import sys

import digest

CANDIDATES = {
    "geopolitics": [
        "https://feeds.npr.org/1004/rss.xml",
        "https://www.theguardian.com/world/rss",
    ],
    "us_economy": [
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://www.bls.gov/feed/bls_latest.rss",
    ],
    "us_jobs": [
        "https://www.bls.gov/feed/empsit.rss",
        "https://www.cnbc.com/id/10000113/device/rss/rss.html",
        "https://www.hrdive.com/feeds/news/",
        "https://www.shrm.org/rss/pages/rss.aspx",
    ],
    "us_real_estate": [
        "https://www.housingwire.com/feed/",
        "https://www.redfin.com/news/feed/",
        "https://www.realtor.com/news/feed/",
        "https://therealdeal.com/feed/",
    ],
    "miami_florida": [
        "https://therealdeal.com/miami/feed/",
        "https://www.miaminewtimes.com/miami/Rss.xml",
        "https://www.miamiherald.com/latest-news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true",
        "https://www.local10.com/arcio/rss/",
        "https://floridaphoenix.com/feed/",
        "https://www.tampabay.com/arcio/rss/",
        "https://www.wlrn.org/rss.xml",
    ],
    "argentina": [
        "https://www.ambito.com/rss/pages/economia.xml",
        "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/",
        "https://www.clarin.com/rss/economia/",
        "https://www.pagina12.com.ar/rss/secciones/economia/notas",
        "https://www.cronista.com/files/rss/economia.xml",
        "https://www.lanacion.com.ar/arcio/rss/category/economia/",
        "https://www.batimes.com.ar/feed",
    ],
    "ai": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://arstechnica.com/ai/feed/",
        "https://hnrss.org/frontpage?points=200",
        "https://openai.com/news/rss.xml",
    ],
    "videogames": [
        "https://www.polygon.com/rss/index.xml",
        "https://www.rockpapershotgun.com/feed",
        "https://kotaku.com/rss",
    ],
    "movies": [
        "https://www.hollywoodreporter.com/feed/",
        "https://www.indiewire.com/feed/",
    ],
}


def main():
    for topic, urls in CANDIDATES.items():
        print(f"## {topic}")
        for url in urls:
            try:
                items = digest.parse_feed(digest.http_get(url, timeout=20, attempts=2))
            except Exception as e:  # dev tool: report everything
                print(f"  FAIL {url}: {type(e).__name__} {str(e)[:80]}")
                continue
            lens = [len(i["snippet"]) for i in items]
            dates = [i["published"] for i in items if i["published"]]
            newest = max(dates).strftime("%m-%d %H:%M") if dates else "n/a"
            med = int(statistics.median(lens)) if lens else 0
            print(f"  ok   {len(items):3d} entries, newest {newest}, median snippet {med:4d} chars  {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
