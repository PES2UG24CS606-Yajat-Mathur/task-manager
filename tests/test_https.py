"""HTTPS / TLS - TC-Sec-03 (TMA-SR-001)."""

from tests.helpers import APITestCase


class TestHttps(APITestCase):
    config_overrides = {"FORCE_HTTPS": True}

    def test_TC_Sec_03_http_redirected_to_https_with_hsts(self):
        resp = self.client.get("/api/tasks", base_url="http://localhost")
        self.assertEqual(resp.status_code, 301)
        self.assertTrue(resp.headers["Location"].startswith("https://"))

        secure = self.client.get("/", base_url="https://localhost")
        self.assertEqual(secure.status_code, 200)
        self.assertIn("max-age=", secure.headers["Strict-Transport-Security"])
        secure.close()

    def test_login_over_plain_http_never_reaches_the_app(self):
        self.register("tls@example.com")       # helpers use the default base_url (http)
        resp = self.client.post("/api/auth/login", base_url="http://localhost",
                                json={"email": "tls@example.com", "password": "Passw0rd1"})
        self.assertIn(resp.status_code, (301, 308))
        self.assertEqual(self.sql("SELECT * FROM sessions"), [])     # no token was issued

    def test_proxy_header_trusted_only_when_configured(self):
        # Without TRUST_PROXY a client cannot fake HTTPS with X-Forwarded-Proto
        resp = self.client.get("/", base_url="http://localhost",
                               headers={"X-Forwarded-Proto": "https"})
        self.assertEqual(resp.status_code, 301)


class TestHttpsBehindProxy(APITestCase):
    config_overrides = {"FORCE_HTTPS": True, "TRUST_PROXY": True}

    def test_forwarded_https_accepted(self):
        with self.client.get("/", base_url="http://localhost",
                             headers={"X-Forwarded-Proto": "https"}) as resp:
            self.assertEqual(resp.status_code, 200)


class TestHttpsDefaults(APITestCase):
    def test_production_forces_https_development_does_not(self):
        from app.config import DevelopmentConfig, ProductionConfig
        self.assertTrue(ProductionConfig.FORCE_HTTPS)
        self.assertFalse(DevelopmentConfig.FORCE_HTTPS)
        with self.client.get("/") as resp:                # tests run without FORCE_HTTPS
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn("Strict-Transport-Security", resp.headers)
