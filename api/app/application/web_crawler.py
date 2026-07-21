"""Safe public-web fetching and readable text extraction."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_WEB_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5


class UnsafeWebUrlError(ValueError):
    """The URL may reach a local, private, or otherwise unsafe network address."""


class WebFetchError(RuntimeError):
    """A public web page could not be downloaded or parsed."""


async def ensure_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeWebUrlError("仅支持公开的 HTTP 或 HTTPS 网页")
    if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        raise UnsafeWebUrlError("网页地址不能包含凭据或非标准端口")
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeWebUrlError("无法解析网页域名") from exc
    addresses = {item[4][0] for item in infos}
    if not addresses:
        raise UnsafeWebUrlError("无法解析网页域名")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise UnsafeWebUrlError("网页地址无效") from exc
        if not address.is_global:
            raise UnsafeWebUrlError("不允许访问本机、内网或保留地址")


async def fetch_web_page(url: str) -> tuple[str, str, str]:
    current = url
    headers = {
        "User-Agent": "Mozilla/5.0 AvpilotKnowledgeBot/0.4",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await ensure_public_url(current)
            try:
                async with client.stream("GET", current, headers=headers) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise WebFetchError("网页重定向缺少目标地址")
                        current = urljoin(current, location)
                        continue
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise WebFetchError(f"网页返回 HTTP {response.status_code}") from exc
                    content_type = response.headers.get("content-type", "").lower()
                    if (
                        "text/html" not in content_type
                        and "application/xhtml+xml" not in content_type
                    ):
                        raise WebFetchError("该地址不是 HTML 网页")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > MAX_WEB_BYTES:
                            raise WebFetchError("网页内容超过 5 MB 限制")
                        chunks.append(chunk)
                    encoding = response.encoding or "utf-8"
                    html = b"".join(chunks).decode(encoding, errors="replace")
                    title, text = extract_web_text(html, current)
                    return title, text, current
            except WebFetchError:
                raise
            except httpx.HTTPError as exc:
                raise WebFetchError(f"网页抓取失败：{exc}") from exc
    raise WebFetchError("网页重定向次数过多")


def extract_web_text(html: str, fallback_title: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "canvas", "nav", "footer"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else fallback_title
    root = soup.find("article") or soup.find("main") or soup.body or soup
    lines = [line.strip() for line in root.get_text("\n").splitlines() if line.strip()]
    text = "\n".join(dict.fromkeys(lines))
    if len(text) < 40:
        raise WebFetchError("未能从网页提取到足够的正文")
    return title[:512], text
