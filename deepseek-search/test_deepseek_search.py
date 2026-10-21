"""DeepSeek Search & Fetch CLI の単体テスト。ネットワークは使わない。"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import deepseek_search as ds


class FakeResponse:
    def __init__(self, status_code, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class ValidationTests(unittest.TestCase):
    def test_build_query_adds_site_operator(self):
        self.assertEqual(
            ds.build_query("AI", "https://example.substack.com/"),
            "AI site:example.substack.com",
        )

    def test_build_query_site_only(self):
        self.assertEqual(ds.build_query("", "example.substack.com"), "site:example.substack.com")

    def test_build_query_rejects_blank(self):
        with self.assertRaises(ds.DeepSeekError):
            ds.build_query("   ", None)

    def test_validate_url_rejects_userinfo_and_bad_scheme(self):
        with self.assertRaises(ds.DeepSeekError):
            ds.validate_url("https://user:pass@example.com/a")
        with self.assertRaises(ds.DeepSeekError):
            ds.validate_url("ftp://example.com/a")

    def test_validate_count_bounds(self):
        self.assertEqual(ds.validate_count(50), 50)
        with self.assertRaises(ds.DeepSeekError):
            ds.validate_count(0)


class ClientTests(unittest.TestCase):
    def test_search_posts_expected_body(self):
        session = mock.Mock()
        session.headers = {}
        session.post.return_value = FakeResponse(
            200,
            {
                "results": [
                    {
                        "title": "記事",
                        "url": "https://example.com/p/one",
                        "snippet": "短い要約",
                        "summary": "長い要約",
                        "content": "",
                        "rerank_score": 2.1,
                        "authority": 3,
                        "date": None,
                        "site_name": "Example",
                        "site_icon": None,
                    }
                ]
            },
        )
        client = ds.DeepSeekClient("test-key", session=session, sleeper=lambda _seconds: None)
        results = client.search(
            "AI",
            count=3,
            ori_question="最新の記事は？",
            localization="203.0.113.8",
            need_content=False,
        )
        self.assertEqual(results[0]["url"], "https://example.com/p/one")
        _args, kwargs = session.post.call_args
        self.assertEqual(kwargs["json"]["query"], "AI")
        self.assertEqual(kwargs["json"]["count"], 3)
        self.assertEqual(kwargs["json"]["ori_question"], "最新の記事は？")
        self.assertEqual(kwargs["json"]["localization"], "203.0.113.8")
        self.assertFalse(kwargs["json"]["need_content"])
        self.assertEqual(session.headers["Authorization"], "Bearer test-key")

    def test_fetch_returns_title_and_content(self):
        session = mock.Mock()
        session.headers = {}
        session.post.return_value = FakeResponse(
            200,
            {"title": "Example", "content": "# Example\n\n本文"},
        )
        client = ds.DeepSeekClient("test-key", session=session)
        page = client.fetch("https://example.com/a")
        self.assertEqual(page["title"], "Example")
        self.assertIn("本文", page["content"])
        self.assertEqual(session.post.call_args.kwargs["json"], {"url": "https://example.com/a"})

    def test_retries_429_then_succeeds(self):
        session = mock.Mock()
        session.headers = {}
        session.post.side_effect = [
            FakeResponse(429, {"error": {"message": "slow down", "code": "rate_limit"}}, headers={"Retry-After": "0"}),
            FakeResponse(200, {"results": []}),
        ]
        sleeper = mock.Mock()
        client = ds.DeepSeekClient("test-key", session=session, sleeper=sleeper)
        self.assertEqual(client.search("AI"), [])
        self.assertEqual(session.post.call_count, 2)
        sleeper.assert_called_once_with(0.0)

    def test_does_not_retry_400(self):
        session = mock.Mock()
        session.headers = {}
        session.post.return_value = FakeResponse(
            400,
            {"error": {"message": "bad query", "type": "invalid_request_error", "code": "invalid_request_error"}},
        )
        client = ds.DeepSeekClient("test-key", session=session, sleeper=lambda _seconds: None)
        with self.assertRaises(ds.DeepSeekError) as caught:
            client.search("AI")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(session.post.call_count, 1)

    def test_run_fetches_each_unique_url_and_writes_markdown(self):
        session = mock.Mock()
        session.headers = {}
        session.post.side_effect = [
            FakeResponse(
                200,
                {
                    "results": [
                        {
                            "title": "一つ目",
                            "url": "https://example.substack.com/p/one",
                            "snippet": "s1",
                            "summary": "sum1",
                            "content": "",
                            "rerank_score": 2.0,
                            "authority": 2,
                            "date": "2026-01-01T00:00:00+00:00",
                            "site_name": "Letters",
                            "site_icon": None,
                        },
                        {
                            "title": "取得失敗",
                            "url": "https://example.substack.com/p/hidden",
                            "snippet": "s2",
                            "summary": "有料の可能性",
                            "content": "",
                            "rerank_score": 1.2,
                            "authority": 1,
                            "date": None,
                            "site_name": "Letters",
                            "site_icon": None,
                        },
                    ]
                },
            ),
            FakeResponse(200, {"title": "一つ目の本文", "content": "公開されている本文"}),
            FakeResponse(404, {"error": {"message": "page unavailable", "code": "not_found"}}),
        ]
        client = ds.DeepSeekClient("test-key", session=session, sleeper=lambda _seconds: None)
        with tempfile.TemporaryDirectory() as tmp:
            items = ds.search_and_fetch(
                client,
                "site:example.substack.com",
                count=10,
                ori_question=None,
                localization=None,
                need_content=False,
                max_fetch=None,
                delay=0,
            )
            self.assertIsNone(items[0]["fetch_error"])
            self.assertEqual(items[0]["fetched_content"], "公開されている本文")
            self.assertEqual(items[1]["fetch_error"], "page unavailable")
            paths = ds.write_pages(items, Path(tmp))
            text = paths[0].read_text(encoding="utf-8")
            self.assertIn("公開されている本文", text)
            self.assertIn("https://example.substack.com/p/one", text)
            failed = paths[1].read_text(encoding="utf-8")
            self.assertIn("page unavailable", failed)
            self.assertIn("有料の可能性", failed)

    def test_cli_search_json(self):
        with mock.patch.object(ds, "load_api_key", return_value="test-key"):
            with mock.patch.object(ds, "DeepSeekClient") as client_cls:
                client_cls.return_value.search.return_value = [
                    {"title": "T", "url": "https://example.com", "snippet": "s"}
                ]
                buffer = io.StringIO()
                with mock.patch("sys.stdout", buffer):
                    code = ds.main(
                        ["--api-key", "test-key", "search", "DeepSeek", "--count", "2", "--json"]
                    )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["results"][0]["title"], "T")
        client_cls.return_value.search.assert_called_once()


if __name__ == "__main__":
    unittest.main()
