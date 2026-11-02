import requests

class OllamaClient:
    def __init__(self, base_url, model, timeout=120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def health(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
            return True, names
        except Exception as exc:
            return False, str(exc)

    def generate(self, prompt, system=None):
        payload = {
            "model": self.model,
            "stream": False,
            "messages": ([{"role": "system", "content": system}] if system else []) +
                        [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.2}
        }
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "").strip()
