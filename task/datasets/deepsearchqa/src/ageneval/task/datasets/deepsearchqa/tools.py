"""Live web tools for DeepSearchQA (search + page fetch).

DeepSearchQA is an open-web benchmark. Problems name the source sites
(NHS, federalreserve.gov, Vision of Humanity, World Population Review, …).
``web_search`` is a general web index that must return those official URLs;
it must not substitute Wikipedia (or any other site) for them.
``open_url`` fetches whatever URL the agent or search result provides.

The cluster has no direct egress. ``tau_env.sh`` clears ``http_proxy`` so
localhost / the model gateway stay off a broken proxy. That means a shell
``source setup_proxy.sh`` does **not** automatically reach this module:
this file installs the institutional proxy on the opener itself.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_TIMEOUT = 15
_SEARCH_TIMEOUT = 12
_CLUSTER_PROXY = "http://httpproxy-headless.kubebrain.svc.pjlab.local:3128"
# In-process cache: same canonical URL is not fetched again (404 and
# timeouts included). This is the network-side fix for "retry the same URL".
_PAGE_CACHE: dict[str, dict[str, Any]] = {}


def _proxy_url() -> str | None:
    for key in ("https_proxy", "http_proxy", "HTTPS_PROXY", "HTTP_PROXY"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return os.environ.get("A2E_WEB_PROXY", _CLUSTER_PROXY)


def _ensure_process_proxy() -> str | None:
    """Put the cluster proxy into this process even if tau_env.sh wiped it."""
    proxy = _proxy_url()
    if not proxy:
        return None
    if not (os.environ.get("http_proxy") or "").strip():
        os.environ["http_proxy"] = proxy
        os.environ["HTTP_PROXY"] = proxy
    if not (os.environ.get("https_proxy") or "").strip():
        os.environ["https_proxy"] = proxy
        os.environ["HTTPS_PROXY"] = proxy
    no_proxy = os.environ.get("no_proxy") or ""
    extra = "127.0.0.1,localhost,10.0.0.0/8,.pjlab.org.cn,35.220.164.252"
    merged = ",".join(x for x in (no_proxy, extra) if x)
    os.environ["no_proxy"] = merged
    os.environ["NO_PROXY"] = merged
    return proxy


def _opener() -> urllib.request.OpenerDirector:
    proxy = _ensure_process_proxy()
    handlers: list[urllib.request.BaseHandler] = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def get_deepsearchqa_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the open web and return official source URLs. "
                    "Prefer the websites named in the question "
                    "(NHS, Federal Reserve, Supreme Court, Vision of Humanity, …). "
                    "Do not replace those sources with a different site."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query, as specific as possible.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_url",
                "description": (
                    "Fetch a URL and return extracted visible text (truncated). "
                    "Use the official page named in the question or returned by web_search."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "http(s) URL to open.",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
    ]


def _headers(accept: str) -> dict[str, str]:
    return {
        "User-Agent": _UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }


def _request(
    url: str,
    *,
    accept: str = "text/html,application/xhtml+xml,application/json",
    timeout: float | None = None,
) -> bytes:
    """GET through the cluster proxy. Prefer requests (redirects + proxy).

    One retry on timeout / connection error. 404 is not retried.
    """
    timeout = timeout or _TIMEOUT
    proxy = _ensure_process_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    headers = _headers(accept)
    last: Exception | None = None
    try:
        import requests

        for _attempt in range(2):
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    proxies=proxies,
                    allow_redirects=True,
                )
                if resp.status_code == 404:
                    raise urllib.error.HTTPError(url, 404, "Not Found", resp.headers, None)
                if resp.status_code >= 400:
                    raise urllib.error.HTTPError(
                        url, resp.status_code, resp.reason or "error", resp.headers, None
                    )
                return resp.content
            except (requests.Timeout, requests.ConnectionError) as exc:
                last = exc
                continue
    except ImportError:
        last = None
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with _opener().open(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        if last is not None:
            raise last from exc
        raise


def _unwrap_href(href: str) -> str:
    href = html.unescape(href or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    qs = urllib.parse.parse_qs(parsed.query)
    for key in ("uddg", "u", "url"):
        if qs.get(key):
            return qs[key][0]
    return href


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(value or "")).strip()


def _open_web_search(query: str) -> list[dict[str, str]]:
    """General web index. Results are the live pages, not a substitute corpus."""
    url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
    html_text = _request(url, accept="text/html", timeout=_SEARCH_TIMEOUT).decode(
        "utf-8", errors="replace"
    )
    hits: list[dict[str, str]] = []
    for m in re.finditer(
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        re.I | re.S,
    ):
        href = _unwrap_href(m.group(1))
        if not href.startswith("http") or "duckduckgo.com" in href:
            continue
        title = _strip_tags(m.group(2))
        if not title:
            continue
        hits.append({"title": title, "snippet": "", "url": href})
        if len(hits) >= 8:
            break
    return hits


def _ddg_html_search(query: str) -> list[dict[str, str]]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    html_text = _request(url, accept="text/html", timeout=_SEARCH_TIMEOUT).decode(
        "utf-8", errors="replace"
    )
    hits: list[dict[str, str]] = []
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        re.I | re.S,
    ):
        href = _unwrap_href(m.group(1))
        if not href.startswith("http") or "duckduckgo.com" in href:
            continue
        title = _strip_tags(m.group(2))
        if not title:
            continue
        hits.append({"title": title[:200], "snippet": "", "url": href})
        if len(hits) >= 8:
            break
    return hits


def _web_search(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"error": "empty query"}
    errors: list[str] = []
    for source, fn in (("open_web", _open_web_search), ("open_web_html", _ddg_html_search)):
        try:
            hits = fn(q)
        except urllib.error.HTTPError as exc:
            errors.append(f"{source}: HTTP {exc.code}")
            continue
        except Exception as exc:  # noqa: BLE001 — requests.Timeout is not URLError
            errors.append(f"{source}: {exc}")
            continue
        if hits:
            return {
                "query": q,
                "source": source,
                "results": hits,
                "proxy": bool(_proxy_url()),
            }
    return {"query": q, "results": [], "error": "; ".join(errors) or "no results"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()


def _open_url(url: str) -> dict[str, Any]:
    from ageneval.task.core.native_tools import canonicalize_url

    raw_url = (url or "").strip()
    if not raw_url.startswith(("http://", "https://")):
        return {"error": "url must start with http:// or https://"}
    target = canonicalize_url(raw_url)
    cached = _PAGE_CACHE.get(target)
    if cached is not None:
        return {**cached, "cached": True}
    try:
        raw = _request(target, accept="text/html,application/xhtml+xml")
    except urllib.error.HTTPError as exc:
        payload = {
            "error": f"HTTP {exc.code}",
            "url": target,
            "reason": str(exc.reason),
            "hint": "Use a URL returned by web_search; do not guess dated paths.",
        }
        _PAGE_CACHE[target] = payload
        return payload
    except Exception as exc:  # noqa: BLE001 — requests.Timeout is not URLError
        payload = {"error": f"fetch failed: {exc}", "url": target}
        _PAGE_CACHE[target] = payload
        return payload
    page = raw.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    try:
        parser.feed(page)
    except Exception as exc:  # noqa: BLE001
        payload = {"error": f"html parse failed: {exc}", "url": target}
        _PAGE_CACHE[target] = payload
        return payload
    text = parser.text()[:8000]
    payload = {"url": target, "text": text, "chars": len(text)}
    _PAGE_CACHE[target] = payload
    return payload


def deepsearchqa_tool_executor(
    name: str, arguments: Mapping[str, Any], state: Mapping[str, Any]
) -> Any:
    args = dict(arguments or {})
    if name == "web_search":
        return _web_search(str(args.get("query") or ""))
    if name == "open_url":
        return _open_url(str(args.get("url") or ""))
    return {"error": f"unknown tool '{name}'", "available": ["web_search", "open_url"]}
