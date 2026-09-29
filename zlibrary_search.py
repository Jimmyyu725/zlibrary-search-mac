#!/usr/bin/env python3
"""批次搜尋、自動下載並匯出 CSV。Python 3.10 以上。

安裝：python3 -m pip install zlibrary==1.0.2
執行：python3 zlibrary_search.py

修改下方 KEYWORDS，或在同目錄建立 keywords.txt，每行一個關鍵字。
帳號可使用 ZLIB_EMAIL、ZLIB_PASSWORD 環境變數，否則互動輸入。
介面依據：https://github.com/sertraline/zlibrary
此為非官方套件；網站改版可能導致登入、搜尋或解析失敗。
檔案存入 downloads。鏈結可能失效；登入頁面或錯誤頁面不會當作書籍保存。
"""

import asyncio
import csv
import getpass
import hashlib
import inspect
import os
import re
import tempfile
from pathlib import Path
import sys
from urllib.parse import urljoin, urlparse

KEYWORDS = ["machine learning", "金融學", "Python"]
KEYWORDS_FILE = Path(__file__).with_name("keywords.txt")
OUTPUT_FILE = Path(__file__).with_name("zlibrary_results.csv")
DOWNLOAD_DIR = Path(__file__).with_name("downloads")
AUTO_DOWNLOAD = True
MAX_FILE_BYTES = 512 * 1024 * 1024
DOWNLOAD_TIMEOUT = 300.0
MAX_RESULTS_PER_KEYWORD = 30
BATCH_SIZE = 10
MAX_BATCHES = 10
REQUEST_INTERVAL = 2.0
REQUEST_TIMEOUT = 60.0

FIELDS = ["keyword", "id", "title", "authors", "year", "language",
          "format", "size", "book_url", "download_url", "status", "error",
          "local_file", "download_status", "download_error"]


def cell(value):
    text = "" if value is None else str(value)
    # 防止書名等外部文字被試算表軟體解讀成公式。
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def http_url(value, base=""):
    if not value or str(value) == "CONVERSION_NEEDED" or str(value).startswith("Unavailable"):
        return ""
    if not str(value).startswith(("http://", "https://", "/")):
        return ""
    candidate = urljoin(base, str(value))
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in ("http", "https") and parsed.netloc else ""


def authors_text(value):
    if isinstance(value, list):
        return "; ".join(str(a.get("author", "")) if isinstance(a, dict)
                         else str(a) for a in value)
    return value or ""


class Pacer:
    def __init__(self):
        self.last = None

    async def call(self, operation, *args, _timeout=REQUEST_TIMEOUT, **kwargs):
        loop = asyncio.get_running_loop()
        if self.last is not None:
            await asyncio.sleep(max(0, REQUEST_INTERVAL - (loop.time() - self.last)))
        try:
            return await asyncio.wait_for(operation(*args, **kwargs), _timeout)
        finally:
            self.last = loop.time()


class DownloadBlocked(Exception):
    pass


class InvalidBookResponse(Exception):
    pass


class Downloader:
    def __init__(self, session, directory):
        self.session = session
        self.directory = directory
        self.disabled = False

    async def download(self, row, identity):
        if self.disabled:
            return {"download_status": "paused_after_block"}
        title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(row.get('title') or 'book'))
        title = title.strip(' .')[:90] or 'book'
        suffix = re.sub(r'[^a-z0-9]', '', str(row.get('format') or '').lower())[:12]
        suffix = suffix or 'bin'
        key = hashlib.sha256(identity.encode()).hexdigest()[:16]
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f'{key}_{title}.{suffix}'
        if target.is_file() and target.stat().st_size:
            return {"download_status": "already_exists", "local_file": str(target.resolve())}
        temporary = None
        try:
            async with self.session.get(row['download_url']) as response:
                if response.status in (401, 403, 429):
                    self.disabled = True
                    raise DownloadBlocked()
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type or 'application/json' in content_type:
                    self.disabled = True
                    raise InvalidBookResponse()
                expected = response.content_length
                if expected is not None and expected > MAX_FILE_BYTES:
                    raise ValueError('File size limit')
                try:
                    first = await response.content.readexactly(4096)
                except asyncio.IncompleteReadError as exc:
                    first = exc.partial
                probe = first.lstrip().lower()
                if not first or probe.startswith((b'<!doctype html', b'<html', b'{"')):
                    self.disabled = True
                    raise InvalidBookResponse()
                if len(first) > MAX_FILE_BYTES:
                    raise ValueError('File size limit')
                # 常見書籍格式增加檔頭檢查，避免把錯誤訊息當成檔案。
                if suffix == 'pdf' and b'%PDF-' not in first[:1024]:
                    raise InvalidBookResponse()
                if suffix in ('epub', 'zip') and not first.startswith(b'PK'):
                    raise InvalidBookResponse()
                with tempfile.NamedTemporaryFile(dir=self.directory, suffix='.part', delete=False) as out:
                    temporary = Path(out.name)
                    out.write(first)
                    total = len(first)
                    async for chunk in response.content.iter_chunked(65536):
                        total += len(chunk)
                        if total > MAX_FILE_BYTES:
                            raise ValueError('File size limit')
                        out.write(chunk)
                if expected is not None and total != expected:
                    raise InvalidBookResponse()
                # 原子建立成品，不覆寫其他執行程序已完成的檔案。
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    if not target.is_file() or not target.stat().st_size:
                        raise
                    return {"download_status": "already_exists", "local_file": str(target.resolve())}
                return {"download_status": "downloaded", "local_file": str(target.resolve())}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


async def export(lib, keywords, output, downloader=None):
    pacer = Pacer()
    cache = {}
    downloaded = {}
    failures = 0
    # x 模式避免覆蓋既有結果；UTF-8 BOM 方便 Excel 辨識中文。
    with output.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()

        def write(row):
            writer.writerow({key: cell(row.get(key, "")) for key in FIELDS})
            handle.flush()

        for keyword in keywords:
            print(f"搜尋：{keyword}")
            seen = set()
            count = 0
            try:
                pages = await pacer.call(lib.search, q=keyword, count=BATCH_SIZE)
                for _ in range(MAX_BATCHES):
                    batch = await pacer.call(pages.next)
                    if not batch:
                        break
                    added = 0
                    for item in batch:
                        if count >= MAX_RESULTS_PER_KEYWORD:
                            break
                        data = dict(item)
                        identity = str(data.get("id") or data.get("url") or repr(data))
                        if identity in seen:
                            continue
                        seen.add(identity)
                        added += 1
                        count += 1
                        row = {"keyword": keyword, "status": "ok"}
                        try:
                            if identity not in cache:
                                cache[identity] = dict(await pacer.call(item.fetch))
                            data.update(cache[identity])
                        except Exception as exc:
                            failures += 1
                            row.update(status="detail_error", error=type(exc).__name__)
                        book_url = http_url(data.get("url"))
                        row.update(
                            id=data.get("id"), title=data.get("name"),
                            authors=authors_text(data.get("authors")),
                            year=data.get("year"), language=data.get("language"),
                            format=data.get("extension"), size=data.get("size"),
                            book_url=book_url,
                            download_url=http_url(data.get("download_url"), book_url),
                        )
                        if row["status"] == "ok" and not row["download_url"]:
                            row["status"] = "no_download_link"
                        if downloader is None:
                            row['download_status'] = 'disabled'
                        elif not row['download_url']:
                            row['download_status'] = 'no_link'
                        else:
                            try:
                                if identity not in downloaded:
                                    result = await pacer.call(downloader.download, row, identity,
                                                              _timeout=DOWNLOAD_TIMEOUT)
                                    if result.get('local_file'):
                                        downloaded[identity] = result
                                else:
                                    result = {**downloaded[identity], 'download_status': 'reused'}
                                row.update(result)
                            except Exception as exc:
                                failures += 1
                                row.update(download_status='failed', download_error=type(exc).__name__)
                        write(row)
                    if count >= MAX_RESULTS_PER_KEYWORD or added == 0:
                        break
                if count == 0:
                    write({"keyword": keyword, "status": "no_results"})
            except Exception as exc:
                failures += 1
                # 不輸出原始錯誤內容，以免其中含有帳號或 session token。
                write({"keyword": keyword, "status": "search_error",
                       "error": type(exc).__name__})
            print(f"已輸出 {count} 筆書籍結果")
    return failures


async def main():
    import aiohttp
    from yarl import URL
    import zlibrary

    lines = (KEYWORDS_FILE.read_text(encoding="utf-8-sig").splitlines()
             if KEYWORDS_FILE.exists() else KEYWORDS)
    keywords = list(dict.fromkeys(line.strip() for line in lines
                                 if line.strip() and not line.lstrip().startswith("#")))
    if not keywords:
        raise ValueError("關鍵字清單為空")
    if OUTPUT_FILE.exists():
        print(f"請先重新命名或移走既有檔案：{OUTPUT_FILE}", file=sys.stderr)
        return 1
    email = os.environ.get("ZLIB_EMAIL") or input("Z-Library 電子郵件：").strip()
    password = os.environ.get("ZLIB_PASSWORD") or getpass.getpass("密碼：")
    lib = zlibrary.AsyncZlib()
    try:
        await asyncio.wait_for(lib.login(email, password), REQUEST_TIMEOUT)
        # Cookie 綁定登入後的主機；重新導向到其他主機不會帶走帳號 Cookie。
        jar = aiohttp.CookieJar()
        jar.update_cookies(lib.cookies or {}, response_url=URL(lib.mirror))
        timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT, sock_read=60)
        async with aiohttp.ClientSession(cookie_jar=jar, timeout=timeout,
                                         auto_decompress=False,
                                         headers={'User-Agent': 'Mozilla/5.0',
                                                  'Accept-Encoding': 'identity'}) as session:
            downloader = Downloader(session, DOWNLOAD_DIR) if AUTO_DOWNLOAD else None
            failures = await export(lib, keywords, OUTPUT_FILE, downloader)
        print(f"CSV：{OUTPUT_FILE}")
        print(f"下載資料夾：{DOWNLOAD_DIR}")
        print(f"失敗操作：{failures}；缺少鏈結請查看 status 欄位。")
        return 2 if failures else 0
    finally:
        close = getattr(lib, "aclose", None) or getattr(lib, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("已停止；已寫入的 CSV 結果會保留。", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"執行失敗：{type(exc).__name__}。請檢查套件、網路和登入狀態。",
              file=sys.stderr)
        sys.exit(1)
