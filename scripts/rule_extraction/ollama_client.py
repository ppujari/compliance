"""Ollama HTTP client with JSON extraction, retry/fallback logic."""

from __future__ import annotations
import json, re, sys
from typing import Any

import requests

OLLAMA_BASE_URL = "http://localhost:11434"


def extract_first_json_block(text: str) -> str:
    """
    Extract the first top-level JSON object/array block from a string.
    This is robust to leading/trailing non-JSON text and code fences.
    Returns "" if nothing plausible is found.
    """
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    # Drop fenced code wrapper if present
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I).strip()
    s = re.sub(r"\s*```$", "", s).strip()

    # Find first opening brace/bracket
    start = None
    opener = ""
    for i, ch in enumerate(s):
        if ch == "{" or ch == "[":
            start = i
            opener = ch
            break
    if start is None:
        return ""

    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return s[start : j + 1]
    return ""


def coerce_rules_from_parsed(obj: Any) -> list[dict]:
    """
    Accept multiple common shapes and coerce into a list[dict] (rule-like objects).
    Supported:
      - [ {...}, ... ]
      - {"rules":[...]} or {"items":[...]}
      - bare rule dict  (has "rule_id")   <- Pass 2 single-object response
      - bare clause dict (has "reg_number") <- Pass 1 identification response
      - dict-of-rule_* -> values list
    """
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if "clauses" in obj and isinstance(obj["clauses"], list):
            return [x for x in obj["clauses"] if isinstance(x, dict)]
        if "rules" in obj and isinstance(obj["rules"], list):
            return [x for x in obj["rules"] if isinstance(x, dict)]
        if "items" in obj and isinstance(obj["items"], list):
            return [x for x in obj["items"] if isinstance(x, dict)]
        if "regulations" in obj and isinstance(obj["regulations"], list):
            return [x for x in obj["regulations"] if isinstance(x, dict)]
        # Bare rule dict (Pass 2) or bare clause identification dict (Pass 1)
        if obj.get("rule_id") or obj.get("reg_number"):
            return [obj]
        # dict-of-rule_* (values might be dicts; strings are ignored here)
        vals = list(obj.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals  # type: ignore[return-value]
    return []


class OllamaClient:
    """Wrapper for Ollama API calls with JSON mode and fallback logic."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: int = 120,
                 temperature: float = 0.1, top_p: float = 0.9):
        self.base_url = base_url
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p

    def chat_json_any(self, model: str, system: str, user: str,
                      timeout: int | None = None, debug: bool = False,
                      debug_raw: bool = False) -> Any:
        """Single-call JSON extraction (used by Pass 1 and Pass 2)."""
        url = f"{self.base_url}/api/chat"
        t = timeout or self.timeout
        payload = {
            "model": model,
            "options": {"temperature": self.temperature, "top_p": self.top_p},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
        }
        r = requests.post(url, json=payload, timeout=t)
        r.raise_for_status()
        data = r.json()
        content = (data.get("message", {}) or {}).get("content", "")
        if debug_raw:
            print(content, file=sys.stderr)
        block = extract_first_json_block(content)
        if not block:
            return None
        return json.loads(block)

    def generate_json(self, model: str, system: str, user: str,
                      fewshots: list[tuple[str, list[dict]]] | None = None,
                      timeout: int | None = None, debug: bool = False,
                      debug_raw: bool = False,
                      format_json: bool = True,
                      fewshot_input: str = "",
                      fewshot_output: list | None = None,
                      fewshot_bool_input: str = "",
                      fewshot_bool_output: list | None = None,
                      bad_explanation: str = "") -> list[dict]:
        """Generate endpoint fallback."""
        url = f"{self.base_url}/api/generate"
        t = timeout or self.timeout
        # Build few-shot sections
        fewshot_sections: list[str] = []
        if fewshot_input and fewshot_output is not None:
            fewshot_sections.append(
                f"Example input:\n{fewshot_input}\n\n"
                f"Example output (JSON array):\n{json.dumps(fewshot_output, ensure_ascii=False)}\n"
            )
        if fewshot_bool_input and fewshot_bool_output is not None:
            fewshot_sections.append(
                f"Example input:\n{fewshot_bool_input}\n\n"
                f"Example output (JSON array):\n{json.dumps(fewshot_bool_output, ensure_ascii=False)}\n"
            )
        if fewshots:
            for ex_input, ex_output in fewshots:
                try:
                    fewshot_sections.append(
                        f"Example input:\n{ex_input}\n\n"
                        f"Example output (JSON array):\n{json.dumps(ex_output, ensure_ascii=False)}\n"
                    )
                except Exception:
                    continue
        if bad_explanation:
            fewshot_sections.append(bad_explanation)

        prompt = (
            f"{system}\n\n" + "\n\n".join(fewshot_sections) + "\n\n" +
            f"Now extract for this input:\n{user}\n"
        )
        payload = {
            "model": model,
            "options": {"temperature": self.temperature, "top_p": self.top_p},
            "prompt": prompt,
            "stream": False,
        }
        if format_json:
            payload["format"] = "json"
        if debug:
            print("[DEBUG] calling Ollama /api/generate", file=sys.stderr)
        try:
            r = requests.post(url, json=payload, timeout=t)
            r.raise_for_status()
        except requests.HTTPError as http_err:
            code = http_err.response.status_code if http_err.response is not None else None
            if format_json and (code in (400, 415) or (code is not None and 500 <= code < 600)):
                if debug:
                    print("[DEBUG] /api/generate retrying once with format='json'", file=sys.stderr)
                payload["format"] = "json"
                r = requests.post(url, json=payload, timeout=t)
                r.raise_for_status()
            else:
                raise
        except requests.RequestException:
            if format_json:
                if debug:
                    print("[DEBUG] /api/generate request error -> retrying once", file=sys.stderr)
                r = requests.post(url, json=payload, timeout=t)
                r.raise_for_status()
            else:
                raise
        data = r.json()
        if debug_raw:
            try:
                print("[DEBUG-RAW] /api/generate HTTP JSON BEGIN", file=sys.stderr)
                print(json.dumps(data)[:2000], file=sys.stderr)
                print("[DEBUG-RAW] /api/generate HTTP JSON END", file=sys.stderr)
            except Exception:
                pass
        content = (data.get("response") or "").strip()
        if debug:
            head = content[:300].replace("\n", " ")
            print(f"[DEBUG] /api/generate raw head[300]: {head}", file=sys.stderr)
        if debug_raw:
            print("[DEBUG-RAW] /api/generate full response BEGIN", file=sys.stderr)
            print(content, file=sys.stderr)
            print("[DEBUG-RAW] /api/generate full response END", file=sys.stderr)
        block = extract_first_json_block(content)
        if not block:
            return []
        try:
            parsed = json.loads(block)
        except Exception:
            return []
        return coerce_rules_from_parsed(parsed)

    def chat_json(self, model: str, system: str, user: str,
                  fewshots: list[tuple[str, list[dict]]] | None = None,
                  timeout: int | None = None, debug: bool = False,
                  debug_raw: bool = False,
                  format_json: bool = True,
                  fewshot_input: str = "",
                  fewshot_output: list | None = None,
                  fewshot_bool_input: str = "",
                  fewshot_bool_output: list | None = None,
                  bad_explanation: str = "") -> list[dict]:
        """Chat endpoint with JSON mode. Falls back to generate endpoint on 404."""
        url = f"{self.base_url}/api/chat"
        t = timeout or self.timeout
        messages = [
            {"role": "system", "content": system},
        ]
        if fewshot_input and fewshot_output is not None:
            messages.append({"role": "user", "content": f"Example:\n{fewshot_input}"})
            messages.append({"role": "assistant", "content": json.dumps(fewshot_output, ensure_ascii=False)})
        if fewshot_bool_input and fewshot_bool_output is not None:
            messages.append({"role": "user", "content": f"Example:\n{fewshot_bool_input}"})
            messages.append({"role": "assistant", "content": json.dumps(fewshot_bool_output, ensure_ascii=False)})
        if fewshots:
            for ex_input, ex_output in fewshots:
                try:
                    messages.append({"role": "user", "content": f"Example:\n{ex_input}"})
                    messages.append({"role": "assistant", "content": json.dumps(ex_output, ensure_ascii=False)})
                except Exception:
                    continue
        if bad_explanation:
            messages.append({"role": "user", "content": bad_explanation})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": model,
            "options": {"temperature": self.temperature, "top_p": self.top_p},
            "messages": messages,
            "stream": False,
        }
        if format_json:
            payload["format"] = "json"
        try:
            if debug:
                print("[DEBUG] calling Ollama /api/chat", file=sys.stderr)
            r = requests.post(url, json=payload, timeout=t)
            r.raise_for_status()
        except requests.HTTPError as http_err:
            code = http_err.response.status_code if http_err.response is not None else None
            if code == 404:
                if debug:
                    print("[DEBUG] /api/chat 404 -> fallback to /api/generate", file=sys.stderr)
                return self.generate_json(
                    model, system, user, timeout=t, debug=debug, debug_raw=debug_raw,
                    fewshots=fewshots, format_json=format_json,
                    fewshot_input=fewshot_input, fewshot_output=fewshot_output,
                    fewshot_bool_input=fewshot_bool_input, fewshot_bool_output=fewshot_bool_output,
                    bad_explanation=bad_explanation,
                )
            if code in (400, 415):
                if format_json:
                    if debug:
                        print("[DEBUG] /api/chat schema format not accepted -> retrying with format='json'", file=sys.stderr)
                    payload["format"] = "json"
                    r = requests.post(url, json=payload, timeout=t)
                    r.raise_for_status()
            elif code is not None and 500 <= code < 600:
                if debug:
                    print("[DEBUG] /api/chat 5xx -> fallback to /api/generate", file=sys.stderr)
                return self.generate_json(
                    model, system, user, timeout=t, debug=debug, debug_raw=debug_raw,
                    fewshots=fewshots, format_json=format_json,
                    fewshot_input=fewshot_input, fewshot_output=fewshot_output,
                    fewshot_bool_input=fewshot_bool_input, fewshot_bool_output=fewshot_bool_output,
                    bad_explanation=bad_explanation,
                )
            else:
                raise
        except requests.RequestException:
            if debug:
                print("[DEBUG] /api/chat request error -> fallback to /api/generate", file=sys.stderr)
            return self.generate_json(
                model, system, user, timeout=t, debug=debug, debug_raw=debug_raw,
                fewshots=fewshots, format_json=format_json,
                fewshot_input=fewshot_input, fewshot_output=fewshot_output,
                fewshot_bool_input=fewshot_bool_input, fewshot_bool_output=fewshot_bool_output,
                bad_explanation=bad_explanation,
            )

        data = r.json()
        if debug_raw:
            try:
                print("[DEBUG-RAW] /api/chat HTTP JSON BEGIN", file=sys.stderr)
                print(json.dumps(data)[:2000], file=sys.stderr)
                print("[DEBUG-RAW] /api/chat HTTP JSON END", file=sys.stderr)
            except Exception:
                pass
        content = data.get("message", {}).get("content", "").strip()
        if debug:
            head = content[:300].replace("\n", " ")
            print(f"[DEBUG] /api/chat raw head[300]: {head}", file=sys.stderr)
        if debug_raw:
            print("[DEBUG-RAW] /api/chat full response BEGIN", file=sys.stderr)
            print(content, file=sys.stderr)
            print("[DEBUG-RAW] /api/chat full response END", file=sys.stderr)
        block = extract_first_json_block(content)
        if not block:
            return []
        try:
            parsed = json.loads(block)
        except Exception:
            return []
        return coerce_rules_from_parsed(parsed)
