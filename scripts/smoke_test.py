"""Check the deployed service's public health route and SPA entry point."""
import argparse
import json
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


def get(url: str, timeout: int):
    request = Request(url, headers={"User-Agent": "eventcraft-smoke-test"})
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.headers, response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Public base URL of the deployed service")
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    try:
        health_status, _, health_body = get(f"{base_url}/healthz", args.timeout)
        if health_status != 200 or json.loads(health_body).get("status") != "ok":
            raise RuntimeError("health endpoint returned an unexpected response")

        page_status, page_headers, page_body = get(base_url, args.timeout)
        if page_status != 200 or "text/html" not in page_headers.get("Content-Type", ""):
            raise RuntimeError("application page did not return HTML")
        if b"EventCraft AI" not in page_body:
            raise RuntimeError("application page did not contain the expected title")
    except (URLError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"Smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Smoke test passed: {base_url}/healthz and the application page responded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
