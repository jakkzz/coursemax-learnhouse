"""Opt-in Nginx contract test: cached image only, no host ports/network/volumes."""
import base64
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("runtime", ROOT / "init_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
sys.path.insert(0, str(ROOT))
from native_gateway import native_gateway_config  # noqa: E402

IMAGE = "nginx@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94"


@unittest.skipUnless(os.environ.get("RUN_GATEWAY_DOCKER_TESTS") == "1", "opt-in cached-image test")
class GatewayFixture(unittest.TestCase):
    gated = True

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.name = "learnhouse-gateway-test-" + uuid.uuid4().hex[:12]
        cls.token = "a" * 64
        cls.basic = "Basic " + base64.b64encode(b"evaluator:synthetic-test-only").decode()
        hashed = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input="synthetic-test-only\n", capture_output=True, text=True, check=True).stdout.strip()
        (cls.root / "passwd").write_text("evaluator:" + hashed + "\n")
        (cls.root / "passwd").chmod(0o444)
        config = (runtime.gateway_config("learn.example.com", cls.token) if cls.gated else native_gateway_config("learn.example.com")).replace("http://app:80", "http://127.0.0.1:8081")
        config += '''\nserver {
            listen 127.0.0.1:8081;
            access_log off;
            location / { return 200 "upstream:$http_authorization"; }
            location = /denied { return 401; }
            location = /session {
                add_header Set-Cookie "LH_access=synthetic; Path=/; HttpOnly";
                return 200;
            }
        }\n'''
        (cls.root / "nginx.conf").write_text(config)
        try:
            subprocess.run([
                "docker", "run", "-d", "--rm", "--pull=never", "--network=none",
                "--name", cls.name, "--memory=32m", "--cpus=0.25", "--pids-limit=64",
                "--read-only", "--tmpfs", "/var/cache/nginx:size=8m",
                "--tmpfs", "/var/run:size=1m", "--entrypoint", "nginx",
                "-v", f"{cls.root / 'nginx.conf'}:/etc/nginx/conf.d/default.conf:ro",
                *(["-v", f"{cls.root / 'passwd'}:/run/secrets/preview.htpasswd:ro"] if cls.gated else []),
                IMAGE, "-g", "daemon off;",
            ], capture_output=True, check=True)
            for _ in range(30):
                code, _ = cls.request()
                if code == (401 if cls.gated else 200):
                    return
                time.sleep(0.1)
            raise RuntimeError("Isolated test proxy did not become ready")
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "rm", "-f", cls.name], capture_output=True)
        cls.tmp.cleanup()

    @classmethod
    def request(cls, headers=(), path="/", method="GET"):
        cmd = ["wget", "-S", "-O", "-", "-T", "3"]
        for header in headers:
            cmd += ["--header", header]
        if method == "POST":
            cmd += ["--post-data", "{}"]
        cmd.append("http://127.0.0.1" + path)
        # Test credentials are piped, never printed in a subprocess command line.
        result = subprocess.run(["docker", "exec", "-i", cls.name, "sh"], input=shlex.join(cmd), capture_output=True, text=True)
        output = result.stdout + result.stderr
        matches = re.findall(r"HTTP/1\.[01] (\d{3})", output)
        return int(matches[-1]) if matches else None, output

class GatewayTests(GatewayFixture):
    def test_anonymous_and_wrong_basic_do_not_mint_cookie(self):
        for headers in [(), ("Authorization: Basic " + base64.b64encode(b"evaluator:wrong").decode(),)]:
            code, response = self.request(headers)
            self.assertEqual(code, 401)
            self.assertNotIn("Set-Cookie:", response)

    def test_valid_basic_sets_cookie_without_forwarding_password(self):
        code, response = self.request(("Authorization: " + self.basic,))
        self.assertEqual(code, 200)
        self.assertIn("Set-Cookie: __Host-LH_preview=", response)
        self.assertNotIn("upstream:Basic", response)

    def test_app_bearer_survives_with_preview_cookie(self):
        code, response = self.request((f"Cookie: other=1; __Host-LH_preview={self.token}", "Authorization: Bearer synthetic-app-token"))
        self.assertEqual(code, 200)
        self.assertIn("upstream:Bearer synthetic-app-token", response)

    def test_invalid_cookie_and_bearer_cannot_bypass_gateway(self):
        for cookie in ["b" * 64, self.token + "extra", "prefix" + self.token]:
            code, _ = self.request((f"Cookie: __Host-LH_preview={cookie}", "Authorization: Bearer synthetic-app-token"))
            self.assertEqual(code, 401)

    def test_unauthorized_api_files_and_streams_are_protected(self):
        for path in ["/api/v1/health", "/content/private", "/collab"]:
            code, _ = self.request(path=path)
            self.assertEqual(code, 401)

    def test_upstream_denial_is_not_a_successful_session(self):
        code, response = self.request(("Authorization: " + self.basic,), path="/denied")
        self.assertEqual(code, 401)
        self.assertNotIn("Set-Cookie:", response)

    def test_registration_blocked_even_with_evaluator_cookie(self):
        for path in ["/api/signup", "/api/v1/users/", "/api/v1/users/1"]:
            code, _ = self.request((f"Cookie: __Host-LH_preview={self.token}",), path=path, method="POST")
            self.assertEqual(code, 403)


class NativeGatewayTests(GatewayFixture):
    gated = False

    def test_anonymous_reaches_native_app_without_challenge(self):
        for path in ["/", "/api/v1/health", "/content/synthetic", "/collab"]:
            code, response = self.request(path=path)
            self.assertEqual(code, 200)
            self.assertNotIn("WWW-Authenticate:", response)
            self.assertIn("Max-Age=0", response)
            self.assertIn("noindex, nofollow, noarchive", response)

    def test_stale_preview_cookie_has_no_authority(self):
        code, response = self.request((f"Cookie: __Host-LH_preview={self.token}",))
        self.assertEqual(code, 200)
        self.assertIn("__Host-LH_preview=;", response)
        self.assertNotIn(self.token, response)

    def test_cached_basic_is_stripped(self):
        code, response = self.request(("Authorization: " + self.basic,))
        self.assertEqual(code, 200)
        self.assertNotIn("upstream:Basic", response)

    def test_native_bearer_and_session_cookie_survive(self):
        code, response = self.request(("Authorization: Bearer synthetic-app-token",))
        self.assertEqual(code, 200)
        self.assertIn("upstream:Bearer synthetic-app-token", response)
        code, response = self.request(path="/session")
        self.assertEqual(code, 200)
        self.assertIn("LH_access=synthetic", response)
        self.assertIn("__Host-LH_preview=;", response)

    def test_native_denial_is_preserved(self):
        code, response = self.request(path="/denied")
        self.assertEqual(code, 401)
        self.assertNotIn("WWW-Authenticate:", response)

    def test_signup_remains_blocked(self):
        for path in ["/api/signup", "/api/v1/users/", "/api/v1/users/1"]:
            code, _ = self.request(path=path, method="POST")
            self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
