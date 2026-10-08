"""Web tools: search + fetch + scan for agent tasks."""
import re, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NexusAI/1.0"}

URL_RE = re.compile(r"https?://[^\s<>\"]+")

def extract_urls(text):
    return list(dict.fromkeys(URL_RE.findall(text or "")))

def web_search(query, n=5, timeout=20):
    # DuckDuckGo html endpoint, no key
    try:
        r = requests.post("https://html.duckduckgo.com/html/",
                          data={"q": query}, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        out = []
        for a in soup.select("a.result__a")[:n]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            # DDG wraps links as /l/?uddg=<url>
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                from urllib.parse import unquote
                href = unquote(m.group(1))
            out.append({"title": title, "url": href})
        return out
    except Exception as e:
        return [{"title": f"search error: {e}", "url": ""}]

def web_fetch(url, timeout=20, max_chars=12000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style", "nav", "footer", "noscript"]):
            t.decompose()
        title = (soup.title.string.strip() if soup.title and soup.title.string else url)
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 40]
        clean = "\n".join(lines)[:max_chars]
        links = []
        for a in soup.find_all("a", href=True)[:30]:
            href = urljoin(url, a["href"])
            if href.startswith("http"):
                links.append(href)
        return {"url": url, "title": title, "text": clean, "links": list(dict.fromkeys(links))[:20], "error": ""}
    except Exception as e:
        return {"url": url, "title": url, "text": "", "links": [], "error": str(e)}

def scan_websites(urls, max_chars=12000):
    results = []
    for u in urls[:8]:
        results.append(web_fetch(u.strip().rstrip(".,);"), max_chars=max_chars))
    return results
