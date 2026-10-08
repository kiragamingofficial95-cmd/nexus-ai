"""Free-first LLM client. Default: Pollinations free (no key).
Optional BYOK: any OpenAI-compatible endpoint (OpenRouter, OpenCode Zen for muse-spark-1.3)."""
import requests, json, urllib.parse

POLLINATIONS_URL = "https://text.pollinations.ai/openai"
ZEN_BASE = "https://opencode.ai/zen/v1"
ZEN_MODEL_FREE = "muse-spark-1.3-contributor-free"

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
        # Normalize: users often paste full endpoints (.../chat/completions, .../responses, .../messages)
        base = self.base_url.strip().rstrip("/")
        for suffix in ("/chat/completions", "/responses", "/messages"):
            if base.endswith(suffix):
                base = base[: -len(suffix)].rstrip("/")
        self.base_url = base
        # OpenCode Zen uses OpenAI Responses API, not /chat/completions
        if "opencode.ai" in base:
            model = self.model or ZEN_MODEL_FREE
            # Zen model ids are bare (muse-spark-1.3-contributor-free), strip opencode/ prefix
            model = model.replace("opencode/", "")
            return self._zen_responses(messages, model, max_tokens, timeout)
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

    def _zen_responses(self, messages, model, max_tokens, timeout):
        """OpenCode Zen Responses API: POST {base}/responses {model, instructions, input}."""
        base = self.base_url.strip().rstrip("/")
        for suffix in ("/chat/completions", "/responses", "/messages"):
            if base.endswith(suffix):
                base = base[: -len(suffix)].rstrip("/")
        url = base + "/responses"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # Responses API: system -> instructions; others -> typed input parts
        instructions = ""
        convo = []
        for m in messages:
            if m["role"] == "system":
                instructions = m["content"]
            elif m["role"] in ("user", "assistant", "developer"):
                role = "assistant" if m["role"] == "assistant" else m["role"]
                convo.append({"role": role,
                              "content": [{"type": "input_text", "text": m["content"][:8000]}]})
        payload = {"model": model, "input": convo, "store": False,
                   "max_output_tokens": max_tokens}
        if instructions:
            payload["instructions"] = instructions[:4000]
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        try:
            r.raise_for_status()
        except Exception as e:
            body = (r.text or "")[:800]
            raise RuntimeError(f"Zen {r.status_code}: {body}") from e
        data = r.json()
        # robust parse: output_text | output[].content[] ({type:output_text, text:str|{...}})
        if isinstance(data, dict) and data.get("output_text"):
            return data["output_text"]
        try:
            parts = []
            for item in data.get("output", []):
                for c in (item.get("content") or []):
                    if not isinstance(c, dict):
                        continue
                    t = c.get("text")
                    if isinstance(t, dict):
                        t = t.get("value") or t.get("text")
                    t = t or c.get("output_text")
                    if isinstance(t, str) and t:
                        parts.append(t)
            if parts:
                return "\n".join(parts)
        except Exception:
            pass
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        return json.dumps(data)[:4000]
