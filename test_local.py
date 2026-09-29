import asyncio
import contextlib
import csv
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

import aiohttp
from aiohttp import web

spec = importlib.util.spec_from_file_location('target', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


async def run():
    m.REQUEST_INTERVAL = 0
    assert m.cell('=1+1') == "'=1+1"
    assert m.http_url('javascript:alert(1)') == ''
    assert m.authors_text([{'author': 'A'}, 'B']) == 'A; B'
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        async def serve(request):
            if request.path == '/blocked':
                return web.Response(status=429)
            if request.path == '/html':
                return web.Response(text='<html>Login</html>', content_type='text/html')
            return web.Response(body=b'%PDF-1.4\nlocal-test-only\n', content_type='application/pdf')
        app = web.Application()
        app.router.add_get('/{path}', serve)
        runner = web.AppRunner(app)
        await runner.setup()
        try:
            site = web.TCPSite(runner, '127.0.0.1', 0)
            await site.start()
            base = 'http://127.0.0.1:' + str(runner.addresses[0][1])
            async with aiohttp.ClientSession() as session:
                downloader = m.Downloader(session, root / 'downloads')
                row = dict(title='Test', format='pdf', download_url=base+'/book')
                result = await downloader.download(row, 'one')
                assert result['download_status'] == 'downloaded'
                assert Path(result['local_file']).read_bytes().startswith(b'%PDF-')
                assert (await downloader.download(row, 'one'))['download_status'] == 'already_exists'
                for suffix, error in [('html', m.InvalidBookResponse), ('blocked', m.DownloadBlocked)]:
                    guard = m.Downloader(session, root / suffix)
                    try:
                        await guard.download({**row, 'download_url': base+'/'+suffix}, suffix)
                        raise AssertionError('Bad response was accepted')
                    except error:
                        pass
                    assert guard.disabled
                    assert not list((root / suffix).glob('*'))
                class Book(dict):
                    async def fetch(self):
                        return dict(self)
                class Pages:
                    done = False
                    async def next(self):
                        if self.done:
                            return []
                        self.done = True
                        return [Book(id='two', name='=Test', extension='pdf', url=base+'/info', download_url=base+'/book')]
                class Library:
                    async def search(self, **kwargs):
                        return Pages()
                csvpath = root / 'results.csv'
                with contextlib.redirect_stdout(io.StringIO()):
                    assert await m.export(Library(), ['A', 'B'], csvpath, downloader) == 0
                with csvpath.open(encoding='utf-8-sig') as handle:
                    rows = list(csv.DictReader(handle))
                assert len(rows) == 2
                assert rows[0]['title'] == "'=Test"
                assert rows[0]['download_status'] == 'downloaded'
                assert rows[1]['download_status'] == 'reused'
                assert not list(root.rglob('*.part'))
        finally:
            await runner.cleanup()
        if hasattr(m, 'load_cookie_jar'):
            from yarl import URL
            cookies = root / 'cookies.txt'
            cookies.write_text('# Netscape HTTP Cookie File\n.z-lib.gd\tTRUE\t/\tTRUE\t2147483647\tremix_userid\tfixture-id\n.z-lib.gd\tTRUE\t/\tTRUE\t2147483647\tremix_userkey\tfixture-key\n')
            jar = m.load_cookie_jar(cookies)
            assert len(jar.filter_cookies(URL(m.COOKIE_MIRROR))) == 2
            assert not jar.filter_cookies(URL('https://example.com'))
            from unittest.mock import patch
            keywords = root / 'keywords.txt'
            keywords.write_text('fixture\n')
            existing = root / 'existing.csv'
            existing.write_text('preserved')
            async def fake_export(lib, words, output, downloader):
                assert words == ['fixture']
                assert output != existing and not output.exists()
                assert downloader is None
                output.write_text('new result')
                return 0
            with patch.object(m, 'KEYWORDS_FILE', keywords), \
                 patch.object(m, 'OUTPUT_FILE', existing), \
                 patch.object(m, 'export', fake_export), \
                 contextlib.redirect_stdout(io.StringIO()):
                assert await m.main(search_only=True, cookie_file=cookies) == 0
            assert existing.read_text() == 'preserved'
            cookies.write_text('# Netscape HTTP Cookie File\n')
            try:
                m.load_cookie_jar(cookies)
                raise AssertionError('Missing login cookie was accepted')
            except ValueError:
                pass
    print('PASS: local search/export/download/error handling')
    print('COOKIE_SUPPORT=' + str(hasattr(m, 'load_cookie_jar')))

asyncio.run(run())
