"""Free-first LLM client. Default: Pollinations free (no key).
Optional BYOK: any OpenAI-compatible endpoint (OpenRouter, OpenCode Zen for muse-spark-1.3)."""
import requests, json, urllib.parse

POLLINATIONS_URL = "https://text.pollinations.ai/openai"

SYSTEM = ("You are Nexus AI, a production-grade assistant like Claude. "
"Powered by Muse Spark 1.3 class models. Be accurate, concise, helpful. "
"When asked to scan websites, produce structured observations, key facts, comparison table, risks, and action items. "
"For PC control, explain each step and never run destructive commands without confirmation.")

class LLMClient:
    def __init__(self, mode="free", api_key="", base_url="", model=""):
        self.mode = mode  # free | custom
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.model = model.strip()

    def chat(self, messages, max_tokens=1500, temperature=0.6, timeout=90):
        msgs = [{"role": "system", "content": SYSTEM}] + messages
        if self.mode == "custom" and self.api_key and self.base_url:
            return self._openai_compat(msgs, max_tokens, temperature, timeout)
        return self._pollinations(msgs, max_tokens, temperature, timeout)

    def _pollinations(self, messages, max_tokens, temperature, timeout):
        # 1) OpenAI-compatible POST (may 402 when pool exhausted) -> 2) legacy GET fallback
        try:
            payload = {"model": "openai", "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}
            r = requests.post(POLLINATIONS_URL, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-6:])
            q = urllib.parse.quote(convo[:1500])  # GET stays free only for short prompts
            r = requests.get(f"https://text.pollinations.ai/{q}?model=openai", timeout=timeout)
            r.raise_for_status()
            return r.text

    def _openai_compat(self, messages, max_tokens, temperature, timeout):
        url = self.base_url + "/chat/completions"
        model = self.model or "meta/muse-spark-1.3"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # OpenRouter needs these, harmless elsewhere
        headers["HTTP-Referer"] = "https://nexus-ai.local"
        headers["X-Title"] = "Nexus AI"
        payload = {"model": model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": temperature}
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
