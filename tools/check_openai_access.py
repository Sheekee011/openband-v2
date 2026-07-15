"""Fail fast when the parser's OpenAI key cannot make API requests."""

import json
import os
import sys
import urllib.error
import urllib.request


def main():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("OPENAI_API_KEY is missing from GitHub Actions secrets.")
        return 1

    model = os.getenv("OPENAI_PREFLIGHT_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "max_output_tokens": 16,
        "input": "Reply with the single word ready.",
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response.read()
        print(f"OpenAI parser preflight passed with {model}.")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("error", {}).get("message", body)
        except json.JSONDecodeError:
            message = body
        print(f"OpenAI parser preflight failed (HTTP {exc.code}): {message}")
        if exc.code == 429 and "quota" in message.lower():
            print("Add API billing or credits to the OpenAI project used by this repository secret, then retry the workflow.")
        return 2
    except Exception as exc:
        print(f"OpenAI parser preflight failed: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
