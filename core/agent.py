"""Agent: multi-website scan -> structured summary (the 'scan these websites' task)."""
from .webtools import scan_websites, extract_urls, web_search
from .llm import LLMClient

SCAN_PROMPT = """You are Nexus AI, expert research analyst.
User task: {task}

SOURCES (fetched live):
{context}

Produce a production-grade report in Markdown:
# Summary (3-5 lines)
## Per-site observations
### <site> — key facts, numbers, quotes
## Comparison table
## Risks / caveats / outdated info
## Action items / next steps
## Sources (url list)
Be specific, cite numbers. If a page failed, note it. No hallucinations beyond sources."""

def build_context(pages, per_page=6000):
    parts = []
    for p in pages:
        body = p["text"][:per_page] if not p["error"] else f"FETCH FAILED: {p['error']}"
        parts.append(f"=== {p['title']}\nURL: {p['url']}\n{body}\n")
    return "\n".join(parts)[:30000]

def run_scan_task(user_text, llm: LLMClient, progress=None):
    urls = extract_urls(user_text)
    if not urls:
        # infer search query from task
        q = user_text[:120]
        if progress: progress("No URLs found — web searching...")
        hits = web_search(q, n=5)
        urls = [h["url"] for h in hits if h["url"]]
    if progress: progress(f"Fetching {len(urls)} site(s)...")
    pages = scan_websites(urls)
    if progress: progress("Analyzing with AI...")
    ctx = build_context(pages)
    prompt = SCAN_PROMPT.format(task=user_text, context=ctx)
    try:
        out = llm.chat([{"role": "user", "content": prompt}], max_tokens=2000)
        return out, pages
    except Exception as e:
        # Offline/pool-exhausted fallback: extractive report so the task still completes
        lines = [f"# Summary (offline extractive fallback — AI pool busy: {e})", ""]
        for p in pages:
            snippet = (p["text"][:800] or p["error"]) if p else ""
            lines += [f"## {p['title']}", f"URL: {p['url']}", snippet[:1200], ""]
        lines += ["## Action items", "- Retry AI summary when back online (history keeps sources)."]
        return "\n".join(lines), pages
