"""Standard-library tests. Docker contract tests are separately opt-in."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load("init_runtime")
preflight = load("preflight")


class RuntimeTests(unittest.TestCase):
    def test_reject_unsafe_domains(self):
        for domain in ["http://example.com", "a.com;return 200", "A.com", "a.com/path", "localhost", "a..com", "-a.com"]:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                runtime.validate_domain(domain)

    def test_private_files_and_isolated_defaults(self):
        with tempfile.TemporaryDirectory() as parent:
            target = Path(parent) / "runtime"
            runtime.initialize(target, "learn.example.com", "admin@example.com")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            for path in target.iterdir():
                expected = 0o444 if path.name == "preview.htpasswd" else 0o600
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected)
            env = dict(line.split("=", 1) for line in (target / "app.env").read_text().splitlines())
            env = {k: json.loads(v) for k, v in env.items()}
            self.assertEqual(env["LEARNHOUSE_TENANCY"], "single")
            self.assertNotIn("LEARNHOUSE_COOKIE_DOMAIN", env)
            self.assertEqual(env["LEARNHOUSE_ALLOWED_REGEXP"], r"^https://learn\.example\.com$")
            self.assertEqual(env["LEARNHOUSE_IS_AI_ENABLED"], "false")
            self.assertEqual(env["LEARNHOUSE_NUDGES_ENABLED"], "false")
            self.assertNotIn("LEARNHOUSE_GOOGLE_CLIENT_SECRET", env)
            self.assertNotEqual(env["NEXTAUTH_SECRET"], env["LEARNHOUSE_AUTH_JWT_SECRET_KEY"])
            self.assertNotEqual(env["COLLAB_INTERNAL_KEY"], env["LEARNHOUSE_AUTH_JWT_SECRET_KEY"])
            self.assertTrue((target / "preview.htpasswd").read_text().startswith("evaluator:$6$"))
            with self.assertRaises(FileExistsError):
                runtime.initialize(target, "learn.example.com", "admin@example.com")

    def test_refuse_secrets_in_checkout(self):
        with self.assertRaises(ValueError):
            runtime.initialize(runtime.REPO / "private-test", "learn.example.com", "admin@example.com")

    def test_gateway_cookie_and_bearer_contract(self):
        config = runtime.gateway_config("learn.example.com", "a" * 64)
        self.assertIn("__Host-LH_preview=", config)
        self.assertIn("Secure; HttpOnly; SameSite=Lax", config)
        self.assertIn("add_header Set-Cookie $preview_cookie;", config)
        self.assertNotIn("add_header Set-Cookie $preview_cookie always", config)
        self.assertIn("proxy_set_header Authorization $application_authorization", config)
        self.assertIn("~^POST:/api/signup/?$ 1;", config)
        self.assertNotIn("Domain=", config)

    def test_both_public_routers_suppress_callback_url_logging(self):
        compose = (ROOT / "compose.yaml").read_text()
        for router in ("learnhouse-staging", "learnhouse-staging-http"):
            self.assertIn(f"traefik.http.routers.{router}.observability.accesslogs: 'false'", compose)

    def test_token_injection_rejected(self):
        with self.assertRaises(ValueError):
            runtime.gateway_config("learn.example.com", '"; return 200;')


class ResourceTests(unittest.TestCase):
    def test_hard_floor(self):
        gib = preflight.GIB
        self.assertEqual(preflight.MIN_FREE_GIB, 10)
        self.assertTrue(preflight.blockers(10 * gib - 1, 4 * gib, False))
        self.assertFalse(preflight.blockers(10 * gib, 4 * gib, False))

    def test_pull_reserve(self):
        gib = preflight.GIB
        self.assertTrue(preflight.blockers(12 * gib - 1, 4 * gib, True))
        self.assertFalse(preflight.blockers(12 * gib, 4 * gib, True))

    def test_memory_floor(self):
        self.assertTrue(preflight.blockers(40 * preflight.GIB, 2 * preflight.GIB, False))


if __name__ == "__main__":
    unittest.main()
