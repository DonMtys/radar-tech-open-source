"""Publicação horária de projetos GitHub e notícias de tecnologia verificáveis.

Usa somente a API pública do GitHub e o RSS público do Hacker News.
Cada rodada publica no máximo uma mensagem; o SQLite evita repetição.
"""

from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from src.telegram_bot import get_telegram_config, load_env_file, send_telegram_message


APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
DEFAULT_DB = APP_ROOT / "radar_renda.db"
USER_AGENT = "RadarTechOpenSource/1.0 (public news feed)"
TECH_TERMS = (
    "ai", "agent", "artificial intelligence", "llm", "model", "openai", "anthropic",
    "github", "open source", "software", "developer", "programming", "python",
    "linux", "security", "cyber", "database", "duckdb", "browser", "cloud",
    "robot", "chip", "semiconductor", "hardware", "javascript", "rust", "api",
    "inteligência artificial", "tecnologia", "programação", "código aberto",
)


def _clean(value: Any, limit: int = 280) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()[:limit]


def _https_url(value: str, host: str | None = None) -> str | None:
    parsed = urllib.parse.urlparse(value or "")
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if host and parsed.hostname.lower() not in {host, f"www.{host}"}:
        return None
    return value


def _recent(value: str, now: datetime, hours: int) -> bool:
    try:
        parsed = parsedate_to_datetime(value)
        return now - timedelta(hours=hours) <= parsed.astimezone(timezone.utc) <= now + timedelta(minutes=5)
    except (TypeError, ValueError, OverflowError):
        return False


def _is_tech(title: str) -> bool:
    value = title.lower()
    return any(re.search(r"\b" + re.escape(term) + r"\b", value) for term in TECH_TERMS)


def fetch_github_projects(now: datetime | None = None) -> list[dict[str, Any]]:
    """Busca repositórios novos em temas de IA e ferramentas de desenvolvimento."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=14)).date().isoformat()
    results: dict[str, dict[str, Any]] = {}
    token = os.getenv("GITHUB_TOKEN")
    for topic in ("ai-agent", "developer-tools"):
        query = f"topic:{topic} created:>{cutoff} stars:>=10"
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({
            "q": query, "sort": "stars", "order": "desc", "per_page": 15,
        })
        headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.load(response)
        for item in data.get("items", []):
            repo_url = _https_url(item.get("html_url", ""), "github.com")
            if not repo_url or item.get("archived") or item.get("disabled"):
                continue
            created = (item.get("created_at") or "")[:10]
            try:
                if not (now.date() - timedelta(days=14) <= datetime.fromisoformat(created).date() <= now.date()):
                    continue
            except ValueError:
                continue
            results[repo_url] = {
                "kind": "github", "url": repo_url,
                "title": _clean(item.get("full_name"), 120),
                "description": _clean(item.get("description"), 220),
                "stars": int(item.get("stargazers_count") or 0),
                "language": _clean(item.get("language") or "não informada", 40),
                "published": created,
            }
    return sorted(results.values(), key=lambda row: row["stars"], reverse=True)


def fetch_tech_news(now: datetime | None = None) -> list[dict[str, Any]]:
    """Lê notícias recentes do RSS oficial do Hacker News."""
    now = now or datetime.now(timezone.utc)
    request = urllib.request.Request("https://news.ycombinator.com/rss", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=12) as response:
        root = ET.fromstring(response.read())
    results = []
    for item in root.findall("./channel/item"):
        title = _clean(item.findtext("title"), 180)
        url = _https_url(item.findtext("link") or "")
        published = item.findtext("pubDate") or ""
        if not title or not url or not _is_tech(title) or not _recent(published, now, 48):
            continue
        discussion = _https_url(item.findtext("comments") or "", "news.ycombinator.com")
        results.append({
            "kind": "news", "url": url, "title": title,
            "published": published, "discussion": discussion,
            "source": urllib.parse.urlparse(url).hostname or "fonte original",
        })
    return results


def format_post(item: dict[str, Any]) -> str:
    if item["kind"] == "github":
        description = item["description"] or "O autor ainda não publicou uma descrição."
        return (
            f"📡 RADAR TECH OPEN SOURCE\n🚀 PROJETO NOVO NO GITHUB\n\n{item['title']}\n\n"
            f"Descrição do projeto: {description}\n\n"
            f"⭐ {item['stars']} estrelas • Linguagem: {item['language']}\n"
            f"Criado em: {item['published']}\n\n"
            f"Código e detalhes: {item['url']}"
        )
    discussion = f"\nDiscussão no Hacker News: {item['discussion']}" if item.get("discussion") else ""
    return (
        f"📡 RADAR TECH OPEN SOURCE\n📰 NOTÍCIA DE TECNOLOGIA\n\n{item['title']}\n\n"
        f"Título original • Fonte: {item['source']}\n"
        f"Leia na fonte: {item['url']}{discussion}"
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_channel_posts (
            url TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL,
            sent_at TEXT, telegram_message_id INTEGER
        )
    """)
    conn.commit()
    return conn


def run_news_round(db_path: Path = DEFAULT_DB, *, preview: bool = False,
                   max_daily_posts: int = 48, min_interval_minutes: int = 28,
                   github_fetch=fetch_github_projects,
                   news_fetch=fetch_tech_news, sender=send_telegram_message) -> dict[str, Any]:
    """Seleciona uma publicação inédita e envia no máximo uma por rodada."""
    load_env_file(str(APP_ROOT / ".env"))
    now = datetime.now(timezone.utc)
    conn = _connect(Path(db_path))
    try:
        since = (now - timedelta(hours=24)).isoformat()
        count = conn.execute(
            "SELECT COUNT(*) FROM news_channel_posts WHERE status='sent' AND sent_at>=?", (since,)
        ).fetchone()[0]
        if count >= max_daily_posts:
            return {"status": "daily_limit", "sent": 0, "daily_count": count}
        last_sent = conn.execute(
            "SELECT sent_at FROM news_channel_posts WHERE status='sent' ORDER BY sent_at DESC LIMIT 1"
        ).fetchone()
        if last_sent and not preview and now - datetime.fromisoformat(last_sent[0]) < timedelta(minutes=min_interval_minutes):
            return {"status": "cooldown", "sent": 0, "daily_count": count}

        candidates, errors = [], []
        for fetcher in (github_fetch, news_fetch):
            try:
                candidates.extend(fetcher(now))
            except Exception as exc:
                errors.append(f"{fetcher.__name__}: {exc}")
        if not candidates:
            return {"status": "no_candidates", "sent": 0, "errors": errors}

        used = {row[0] for row in conn.execute("SELECT url FROM news_channel_posts")}
        try:
            used.update(row[0] for row in conn.execute(
                "SELECT url_original FROM noticias WHERE telegram_sent=1"
            ))
        except sqlite3.OperationalError:
            pass  # Banco novo ainda não possui as tabelas do pipeline antigo.
        fresh = [item for item in candidates if item["url"] not in used]
        if not fresh:
            return {"status": "no_new_items", "sent": 0, "errors": errors}
        last = conn.execute(
            "SELECT kind FROM news_channel_posts WHERE status='sent' ORDER BY sent_at DESC LIMIT 1"
        ).fetchone()
        preferred = "news" if last and last[0] == "github" else "github"
        chosen = next((item for item in fresh if item["kind"] == preferred), fresh[0])
        text = format_post(chosen)
        if preview:
            return {"status": "preview", "sent": 0, "item": chosen, "text": text, "errors": errors}

        token, chat_id = get_telegram_config()
        if not token or not chat_id:
            return {"status": "missing_telegram_config", "sent": 0, "errors": errors}
        conn.execute(
            "INSERT OR IGNORE INTO news_channel_posts(url,kind,title,status,created_at) VALUES(?,?,?,?,?)",
            (chosen["url"], chosen["kind"], chosen["title"], "pending", now.isoformat()),
        )
        if conn.total_changes == 0:
            return {"status": "already_reserved", "sent": 0, "errors": errors}
        conn.commit()
        result = sender(text=text, token=token, chat_id=chat_id, mock=False)
        if not result.get("ok"):
            conn.execute("DELETE FROM news_channel_posts WHERE url=? AND status='pending'", (chosen["url"],))
            conn.commit()
            return {"status": "send_failed", "sent": 0, "error": result.get("erro"), "errors": errors}
        message_id = result.get("message_id") or (result.get("result") or {}).get("message_id")
        conn.execute(
            "UPDATE news_channel_posts SET status='sent', sent_at=?, telegram_message_id=? WHERE url=?",
            (datetime.now(timezone.utc).isoformat(), message_id, chosen["url"]),
        )
        conn.commit()
        return {"status": "sent", "sent": 1, "kind": chosen["kind"],
                "url": chosen["url"], "message_id": message_id, "errors": errors}
    finally:
        conn.close()
