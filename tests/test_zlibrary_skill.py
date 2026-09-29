import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'skills/zlibrary-cli'
spec = importlib.util.spec_from_file_location('finish', SKILL / 'scripts/finish_epub.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(path):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml', '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
        z.writestr('book.opf', '<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>1984: A Test Fixture</dc:title><dc:creator>Sample Writer</dc:creator><dc:language>en-US</dc:language></metadata><manifest/><spine/></package>')


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / '01 - 1984 (Sample Writer) (z-library.sk).epub'
    fixture(source)
    before = source.read_bytes()
    result = m.finish(source, '1984', 'Sample Writer', 'en')
    target = Path(result['path'])
    assert target.name == '1984 (Sample Writer).epub'
    assert target.read_bytes() == before and not source.exists()
    assert m.finish(target, '1984', 'Sample Writer', 'en')['validated']
    fixture(source)
    try:
        m.finish(source, '1984', 'Sample Writer', 'en')
        raise AssertionError('Collision was not rejected')
    except FileExistsError:
        assert source.read_bytes() == before and target.read_bytes() == before
    for title, author, language in [('Wrong', 'Sample Writer', 'en'), ('1984', 'Wrong', 'en'), ('1984', 'Sample Writer', 'zh')]:
        try:
            m.finish(source, title, author, language)
            raise AssertionError('Metadata mismatch was not rejected')
        except ValueError:
            assert source.exists()
    bad = root / 'error.epub'
    bad.write_text('<html>Login</html>')
    try:
        m.finish(bad, '1984', 'Sample Writer', 'en')
        raise AssertionError('HTML was accepted')
    except zipfile.BadZipFile:
        pass
    fake = root / 'tool'
    fake.mkdir()
    executable = fake / 'zlib'
    executable.write_text('#!' + sys.executable + '\nimport sys,os\nprint("FAKE_CLI",*sys.argv[1:])\nprint("HOME="+os.environ["HOME"])\n')
    executable.chmod(0o700)
    env = os.environ.copy()
    env['ZLIB_TOOL_ROOT'] = str(fake)
    env['ZLIB_STATE_HOME'] = str(root / 'state')
    run = subprocess.run([sys.executable,str(SKILL/'scripts/zlib.py'),'profile','--json'],env=env,capture_output=True,text=True)
    assert run.returncode == 0 and 'profile --json' in run.stdout and str(root/'state') in run.stdout
    run = subprocess.run([sys.executable,str(SKILL/'scripts/zlib.py'),'login-saved'],env=env,capture_output=True,text=True)
    credentials = json.loads((SKILL/'.credentials.json').read_text())
    assert run.returncode == 0 and '[REDACTED]' in run.stdout
    assert all(value not in run.stdout+run.stderr for value in credentials.values())
    assert (SKILL/'.credentials.json').stat().st_mode & 0o777 == 0o600
print('PASS: EPUB validation, identity checks, no-overwrite rename, numeric title preservation, isolated CLI and credential redaction')
