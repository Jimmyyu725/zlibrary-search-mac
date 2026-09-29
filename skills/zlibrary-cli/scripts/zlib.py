#!/usr/bin/env python3
"""Run the verified local CLI with an isolated session directory."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(os.environ.get(
        "ZLIB_TOOL_ROOT",
        "/Users/jingtianyu/Library/Application Support/ZLibrary/heartleo-test-v0.0.8",
    )).expanduser().resolve()
    binary = root / "zlib"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        print(f"Tool is missing or not executable: {binary}", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["HOME"] = str(Path(os.environ.get("ZLIB_STATE_HOME", str(root / "password-home"))).expanduser().resolve())
    args = sys.argv[1:] or ["--help"]
    if args[0] != "login-saved":
        return subprocess.call([str(binary), *args], cwd=root, env=env)
    if len(args) != 1:
        print("login-saved takes no additional arguments", file=sys.stderr)
        return 2
    credential_file = Path(__file__).resolve().parents[1] / ".credentials.json"
    try:
        credential_file.chmod(0o600)
        credentials = json.loads(credential_file.read_text())
        email, password = credentials["email"], credentials["password"]
        if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
            raise ValueError("Empty credentials")
    except (OSError, ValueError, KeyError, TypeError):
        print("Saved credentials are missing or invalid", file=sys.stderr)
        return 2
    result = subprocess.run(
        [str(binary), "login", "--eapi", "--domain", "https://z-lib.gd",
         "--email", email, "--password", password],
        cwd=root, env=env, capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    for secret in (email, password):
        output = output.replace(secret, "[REDACTED]")
    print(output, end="")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
