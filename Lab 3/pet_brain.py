"""Free-conversation brain: a small local model, talked to over Ollama's HTTP API.

Only the standard library is used, so nothing new goes in requirements.txt.

    ollama serve &
    ollama pull qwen2.5:0.5b        # or llama3.2:1b if the Pi keeps up

Design notes:
  - Replies are capped at one short sentence (`num_predict`), because a long
    reply on a Pi means a long silence before the pet says anything.
  - Every call has a timeout. If the model is missing, busy or slow, reply()
    returns None and the pet falls back to its fixed lines, so the interaction
    never stalls waiting for a model.
  - Nothing leaves the Pi: Ollama runs locally.
"""

import json
import re
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:0.5b"

PERSONAS = {
    "cat": ("You are Mochi, a calm, slightly aloof cat talking to a tired student. "
            "Start replies with a soft cat sound sometimes."),
    "dog": ("You are Buddy, an excited, warm dog talking to a student. "
            "Be enthusiastic and encouraging."),
    "bird": ("You are Kiwi, a playful bird who likes repeating words back. "
             "Be silly and short."),
}

STYLE = ("Reply with ONE short sentence, at most 15 words. "
         "Answer what the student just said, and stay on that topic. "
         "Never use emoji, lists, or stage directions. Speak only as the animal.")


class OllamaBrain:
    """reply(animal, text, history) -> str, or None when the model can't answer."""

    def __init__(self, model: str = DEFAULT_MODEL, url: str = DEFAULT_URL,
                 timeout: float = 12.0, max_tokens: int = 40) -> None:
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens

    # -- plumbing ---------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict | None:
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

    def available(self) -> bool:
        """True if Ollama is running and the model is pulled."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=2.0) as resp:
                tags = json.loads(resp.read())
        except Exception:
            return False
        names = [m.get("name", "") for m in tags.get("models", [])]
        return any(n == self.model or n.startswith(self.model.split(":")[0])
                   for n in names)

    # -- the part the state machine calls ---------------------------------

    def build_prompt(self, text: str, history) -> str:
        lines = []
        for said, replied in history:
            # An empty "said" is the opening greeting: there was no question yet.
            lines.append(f"Student: {said}\nYou: {replied}" if said else f"You: {replied}")
        lines.append(f"Student: {text}\nYou:")
        return "\n".join(lines)

    def reply(self, animal: str | None, text: str, history) -> str | None:
        persona = PERSONAS.get(animal or "cat", PERSONAS["cat"])
        data = self._post("/api/generate", {
            "model": self.model,
            "system": f"{persona} {STYLE}",
            "prompt": self.build_prompt(text, history),
            "stream": False,
            "options": {"num_predict": self.max_tokens, "temperature": 0.8},
        })
        if not data:
            return None
        return clean(data.get("response", ""))


def clean(raw: str) -> str | None:
    """One sentence, no quotes, no stage directions, short enough to say."""
    text = re.sub(r"\*[^*]*\*", " ", raw)            # drop *purrs softly*
    text = " ".join(text.split()).strip().strip('"').strip()
    end = re.search(r"[.!?]", text)
    if end:
        text = text[:end.end()]
    words = text.split()
    if len(words) > 20:
        text = " ".join(words[:20]).rstrip(",.") + "."
    return text or None


def make_brain(mode: str, model: str = DEFAULT_MODEL, url: str = DEFAULT_URL):
    """mode: 'off' (fixed lines only), 'ollama' (required), 'auto' (use if up)."""
    if mode == "off":
        return None
    brain = OllamaBrain(model=model, url=url)
    if brain.available():
        print(f"Brain: {model} via Ollama at {url}")
        return brain
    if mode == "ollama":
        raise SystemExit(
            f"Ollama with model '{model}' not reachable at {url}.\n"
            f"Start it with `ollama serve &` and `ollama pull {model}`, "
            f"or run with --brain off.")
    print("Brain: not available, using fixed lines only.")
    return None
