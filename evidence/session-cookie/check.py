import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from yarl import URL

async def run():
    spec=importlib.util.spec_from_file_location('target',sys.argv[1])
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'cookies.txt'
        p.write_text('# Netscape HTTP Cookie File\n'
            '.z-lib.gd\tTRUE\t/\tTRUE\t2147483647\tremix_userid\tfixture-id\n'
            '.z-lib.gd\tTRUE\t/\tTRUE\t2147483647\tremix_userkey\tfixture-key\n'
            'zh.z-lib.gd\tFALSE\t/\tFALSE\t0\tc_token\tfixture-session\n'
            '.z-lib.gd\tTRUE\t/\tTRUE\t1\texpired\tfixture-expired\n')
        jar=m.load_cookie_jar(p)
        filtered=jar.filter_cookies(URL(m.COOKIE_MIRROR))
        session='c_token' in filtered
        expired='expired' in filtered
        isolated=not jar.filter_cookies(URL('https://example.com'))
        host_only='c_token' not in jar.filter_cookies(URL('https://child.zh.z-lib.gd'))
        print(f'SESSION_COOKIE={session}; EXPIRED_COOKIE={expired}; DOMAIN_ISOLATION={isolated}; HOST_ONLY={host_only}')
        return 0 if session and not expired and isolated and host_only else 1
sys.exit(asyncio.run(run()))
