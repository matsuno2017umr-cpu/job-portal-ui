#!/usr/bin/env python3
"""DeepSeek の Search API と Fetch API を呼ぶ CLI。

Search でウェブページを探し、Fetch で各ページの本文を Markdown として取得する。
API キーは環境変数 DEEPSEEK_API_KEY、またはこのディレクトリの .env に置く。

例:
  python deepseek_search.py search "DeepSeek V4" --count 5
  python deepseek_search.py fetch https://example.com/article
  python deepseek_search.py run --site example.substack.com --count 5 --output output
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.deepseek.com"
SEARCH_PATH = "/v1/tools/search"
FETCH_PATH = "/v1/tools/fetch"
QUERY_MAX_LENGTH = 128
URL_MAX_LENGTH = 8192
COUNT_MIN = 1
COUNT_MAX = 50
# ドキュメントどおり、408 / 429 / 5xx だけ再試行する。
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

SCRIPT_DIR = Path(__file__).resolve().parent


class DeepSeekError(Exception):
    """DeepSeek API または呼び出し前の検証で失敗したときのエラー。"""

    def __init__(self, status_code: int, message: str, code: str | None = None):
        self.status_code = status_code
        self.message = message
        self.code = code
        super().__init__(message)


class DeepSeekClient:
    """Search と Fetch の薄いクライアント。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        timeout: float = 60,
        max_retries: int = 3,
        session: requests.Session | None = None,
        sleeper=time.sleep,
    ):
        if not api_key or not api_key.strip():
            raise DeepSeekError(0, "API キーが空です。DEEPSEEK_API_KEY を設定してください。")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleeper
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            }
        )

    def search(
        self,
        query: str,
        count: int = 10,
        ori_question: str | None = None,
        localization: str | None = None,
        need_content: bool = False,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "query": validate_query(query),
            "count": validate_count(count),
            "need_content": bool(need_content),
        }
        if ori_question is not None and ori_question.strip():
            question = ori_question.strip()
            if not 1 <= len(question) <= QUERY_MAX_LENGTH:
                raise DeepSeekError(
                    0,
                    f"ori_question は 1〜{QUERY_MAX_LENGTH} 文字にしてください。",
                )
            body["ori_question"] = question
        if localization is not None and localization.strip():
            body["localization"] = validate_ip(localization.strip())

        payload = self._post(SEARCH_PATH, body)
        results = payload.get("results")
        if not isinstance(results, list):
            raise DeepSeekError(0, "Search の応答に results 配列がありません。")
        return results

    def fetch(self, url: str) -> dict[str, Any]:
        payload = self._post(FETCH_PATH, {"url": validate_url(url)})
        if "content" not in payload:
            raise DeepSeekError(0, "Fetch の応答に content がありません。")
        return {
            "title": payload.get("title") or "",
            "content": payload.get("content") or "",
        }

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.base_url}{path}"
        last_status = 0
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(endpoint, json=body, timeout=self.timeout)
            except requests.RequestException as exc:
                last_status = 0
                if attempt >= self.max_retries:
                    raise DeepSeekError(0, f"リクエストに失敗しました: {exc}") from exc
                self._sleep(backoff_seconds(attempt, None))
                continue

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise DeepSeekError(200, "応答が JSON ではありません。") from exc
                if not isinstance(payload, dict):
                    raise DeepSeekError(200, "応答の JSON がオブジェクトではありません。")
                return payload

            if response.status_code in RETRYABLE_STATUS and attempt < self.max_retries:
                last_status = response.status_code
                self._sleep(backoff_seconds(attempt, response))
                continue

            raise error_from_response(response)

        raise DeepSeekError(last_status, "再試行の上限に達しました。")


def validate_query(query: str) -> str:
    text = query.strip()
    if not text or text.isspace():
        raise DeepSeekError(0, "query を指定してください。空白のみは使えません。")
    if not 1 <= len(text) <= QUERY_MAX_LENGTH:
        raise DeepSeekError(
            0,
            f"query は 1〜{QUERY_MAX_LENGTH} 文字にしてください（現在 {len(text)} 文字）。",
        )
    return text


def validate_count(count: int) -> int:
    if not isinstance(count, int) or isinstance(count, bool) or not COUNT_MIN <= count <= COUNT_MAX:
        raise DeepSeekError(0, f"count は {COUNT_MIN}〜{COUNT_MAX} の整数にしてください。")
    return count


def validate_ip(value: str) -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise DeepSeekError(0, f"localization は IP アドレスにしてください: {value}") from exc
    return value


def validate_url(url: str) -> str:
    text = url.strip()
    if not text:
        raise DeepSeekError(0, "url を指定してください。")
    if len(text) > URL_MAX_LENGTH:
        raise DeepSeekError(0, f"url は {URL_MAX_LENGTH} 文字以内にしてください。")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DeepSeekError(0, "url はホスト付きの http または https にしてください。")
    if parsed.username is not None or parsed.password is not None:
        raise DeepSeekError(0, "url にユーザー名やパスワードは含められません。")
    return text


def build_query(query: str, site: str | None) -> str:
    text = query.strip()
    if site:
        host = site.strip()
        host = re.sub(r"^https?://", "", host, flags=re.IGNORECASE)
        host = host.strip().strip("/")
        if not host or "/" in host or " " in host:
            raise DeepSeekError(0, f"site はホスト名にしてください: {site}")
        clause = f"site:{host}"
        if clause not in text.split():
            text = f"{text} {clause}".strip()
    return validate_query(text)


def error_from_response(response: requests.Response) -> DeepSeekError:
    message = response.text.strip() or f"HTTP {response.status_code}"
    code = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or message)
            code = error.get("code")
            if code is not None:
                code = str(code)
    return DeepSeekError(response.status_code, message, code)


def backoff_seconds(attempt: int, response: requests.Response | None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return float(2**attempt)


def load_api_key(explicit: str | None) -> str:
    load_dotenv()
    load_dotenv(SCRIPT_DIR / ".env")
    key = (explicit or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise DeepSeekError(
            0,
            "API キーがありません。DEEPSEEK_API_KEY を設定するか、--api-key で渡してください。",
        )
    return key


def slug_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    stem = (parsed.path or "").strip("/").replace("/", "-")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    if not stem:
        stem = "page"
    stem = stem[:80]
    return f"{index:02d}-{stem}.md"


def format_search_result(index: int, result: dict[str, Any]) -> str:
    lines = [
        f"[{index}] {result.get('title') or '(タイトルなし)'}",
        f"URL: {result.get('url') or ''}",
        (
            f"スコア: {result.get('rerank_score')}  "
            f"権威: {result.get('authority')}  "
            f"日付: {result.get('date') or '不明'}  "
            f"サイト: {result.get('site_name') or '不明'}"
        ),
        f"要約: {result.get('snippet') or ''}",
    ]
    summary = result.get("summary") or ""
    if summary and summary != result.get("snippet"):
        lines.append(summary)
    content = result.get("content") or ""
    if content:
        lines.append("")
        lines.append(content)
    return "\n".join(lines)


def page_markdown(result: dict[str, Any], page: dict[str, Any] | None, error: str | None) -> str:
    title = ""
    if page and page.get("title"):
        title = page["title"]
    title = title or result.get("title") or result.get("url") or "無題"
    lines = [
        f"# {title}",
        "",
        f"- URL: {result.get('url') or ''}",
        f"- 公開日: {result.get('date') or '不明'}",
        f"- スコア: {result.get('rerank_score')}",
        f"- 権威: {result.get('authority')}",
        f"- サイト: {result.get('site_name') or '不明'}",
        "",
    ]
    if error:
        lines.append(f"取得エラー: {error}")
        lines.append("")
        if result.get("summary"):
            lines.append(result["summary"])
            lines.append("")
    elif page is not None:
        lines.append(page.get("content") or "")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def search_and_fetch(
    client: DeepSeekClient,
    query: str,
    count: int,
    ori_question: str | None,
    localization: str | None,
    need_content: bool,
    max_fetch: int | None,
    delay: float,
) -> list[dict[str, Any]]:
    results = client.search(
        query,
        count=count,
        ori_question=ori_question,
        localization=localization,
        need_content=need_content,
    )
    selected = results if max_fetch is None else results[:max_fetch]
    seen: set[str] = set()
    combined: list[dict[str, Any]] = []
    fetched = 0
    for result in selected:
        item = dict(result)
        url = item.get("url") or ""
        if not url or url in seen:
            item["fetched_title"] = ""
            item["fetched_content"] = ""
            item["fetch_error"] = None if url else "URL がないため取得できません。"
            combined.append(item)
            continue
        seen.add(url)
        if fetched and delay > 0:
            time.sleep(delay)
        fetched += 1
        try:
            page = client.fetch(url)
        except DeepSeekError as exc:
            item["fetched_title"] = ""
            item["fetched_content"] = ""
            item["fetch_error"] = exc.message
        else:
            item["fetched_title"] = page["title"]
            item["fetched_content"] = page["content"]
            item["fetch_error"] = None
        combined.append(item)
    return combined


def write_pages(items: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, item in enumerate(items, start=1):
        page = None
        if item.get("fetch_error") is None and item.get("url"):
            page = {
                "title": item.get("fetched_title") or "",
                "content": item.get("fetched_content") or "",
            }
        path = output_dir / slug_from_url(item.get("url") or "", index)
        path.write_text(
            page_markdown(item, page, item.get("fetch_error")),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def print_json(payload: Any) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def command_search(client: DeepSeekClient, args: argparse.Namespace) -> int:
    query = build_query(args.query or "", args.site)
    results = client.search(
        query,
        count=args.count,
        ori_question=args.ori_question,
        localization=args.localization,
        need_content=args.need_content,
    )
    if args.json:
        print_json({"results": results})
        return 0
    if not results:
        print("該当するページはありませんでした。", file=sys.stderr)
        return 0
    print(f"クエリ: {query}")
    print(f"{len(results)} 件")
    print()
    for index, result in enumerate(results, start=1):
        print(format_search_result(index, result))
        print()
    return 0


def command_fetch(client: DeepSeekClient, args: argparse.Namespace) -> int:
    pages = []
    exit_code = 0
    for index, url in enumerate(args.urls):
        if index and args.delay > 0:
            time.sleep(args.delay)
        try:
            page = client.fetch(url)
        except DeepSeekError as exc:
            exit_code = 1
            print(f"{url}: {exc.message}", file=sys.stderr)
            pages.append({"url": url, "title": "", "content": "", "error": exc.message})
            continue
        pages.append({"url": url, "title": page["title"], "content": page["content"], "error": None})
    if args.json:
        print_json({"pages": pages})
        return exit_code
    for page in pages:
        if page["error"]:
            continue
        print(f"# {page['title'] or '(タイトルなし)'}")
        print(page["url"])
        print()
        print(page["content"])
        print()
    return exit_code


def command_run(client: DeepSeekClient, args: argparse.Namespace) -> int:
    query = build_query(args.query or "", args.site)
    items = search_and_fetch(
        client,
        query,
        count=args.count,
        ori_question=args.ori_question,
        localization=args.localization,
        need_content=args.need_content,
        max_fetch=args.max_fetch,
        delay=args.delay,
    )
    failures = [item for item in items if item.get("fetch_error")]
    if args.output:
        paths = write_pages(items, Path(args.output))
        for path in paths:
            print(path, file=sys.stderr)
    if args.json:
        print_json({"query": query, "results": items})
    elif not args.output:
        print(f"クエリ: {query}")
        if not items:
            print("該当するページはありませんでした。")
        for index, item in enumerate(items, start=1):
            print(format_search_result(index, item))
            if item.get("fetch_error"):
                print(f"取得エラー: {item['fetch_error']}")
            elif item.get("fetched_content"):
                print()
                heading = item.get("fetched_title") or ""
                if heading:
                    print(f"# {heading}")
                print(item["fetched_content"])
            print()
    if failures:
        print(f"{len(failures)} 件の取得に失敗しました。", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DeepSeek の Search API と Fetch API でウェブページを検索し、本文を Markdown で取得します。",
    )
    parser.add_argument("--api-key", help="DeepSeek API キー。省略時は DEEPSEEK_API_KEY")
    parser.add_argument("--base-url", default=BASE_URL, help=f"API のベース URL（既定: {BASE_URL}）")
    parser.add_argument("--timeout", type=float, default=60, help="1 リクエストのタイムアウト秒（既定: 60）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_search_options(target: argparse.ArgumentParser, query_help: str) -> None:
        target.add_argument("query", nargs="?", default="", help=query_help)
        target.add_argument("--site", help="このホストに限定する（site: 演算子を付与）")
        target.add_argument("--count", type=int, default=10, help="検索件数。1〜50（既定: 10）")
        target.add_argument("--ori-question", help="検索のきっかけになった元の質問（128 文字以内）")
        target.add_argument("--localization", help="結果の地域調整に使う IP アドレス")
        target.add_argument(
            "--need-content",
            action="store_true",
            help="Search の応答にページ本文を含める",
        )
        target.add_argument("--json", action="store_true", help="JSON で出力する")

    search_parser = subparsers.add_parser("search", help="クエリに合うページを検索する")
    add_search_options(search_parser, "検索クエリ（1〜128 文字）。--site だけでも可")

    fetch_parser = subparsers.add_parser("fetch", help="URL の本文を Markdown で取得する")
    fetch_parser.add_argument("urls", nargs="+", help="取得する http(s) URL")
    fetch_parser.add_argument("--delay", type=float, default=0, help="連続取得の間隔（秒）")
    fetch_parser.add_argument("--json", action="store_true", help="JSON で出力する")

    run_parser = subparsers.add_parser("run", help="検索し、見つかった URL の本文を取得する")
    add_search_options(run_parser, "検索クエリ（1〜128 文字）。--site だけでも可")
    run_parser.add_argument("--max-fetch", type=int, help="本文を取得する最大件数。省略時は検索結果のすべて")
    run_parser.add_argument("--delay", type=float, default=0, help="Fetch と Fetch の間隔（秒）")
    run_parser.add_argument("--output", help="本文を Markdown ファイルとして書き出すディレクトリ")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {"search", "run"}:
            validate_count(args.count)
            if args.command == "run" and args.max_fetch is not None and args.max_fetch < 1:
                raise DeepSeekError(0, "--max-fetch は 1 以上にしてください。")
        client = DeepSeekClient(
            load_api_key(args.api_key),
            base_url=args.base_url,
            timeout=args.timeout,
        )
        if args.command == "search":
            return command_search(client, args)
        if args.command == "fetch":
            return command_fetch(client, args)
        return command_run(client, args)
    except DeepSeekError as exc:
        print(exc.message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
