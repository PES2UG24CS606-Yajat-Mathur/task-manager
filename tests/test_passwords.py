"""Password storage - TC-Sec-02 (TMA-SR-002, TMA-NF-003)."""

import glob

from tests.helpers import DEFAULT_PASSWORD, APITestCase


class TestPasswordStorage(APITestCase):
    def test_TC_Sec_02_passwords_stored_only_as_hashes(self):
        self.register("hash@example.com", password=DEFAULT_PASSWORD)
        stored = self.sql("SELECT password_hash FROM users")[0]["password_hash"]
        self.assertNotEqual(stored, DEFAULT_PASSWORD)
        self.assertNotIn(DEFAULT_PASSWORD, stored)
        self.assertRegex(stored, r"^(pbkdf2|scrypt):")          # salted KDF format
        # Scan the WHOLE database (main file + write-ahead log) for the plaintext password
        for path in glob.glob(self.db_path + "*"):
            with open(path, "rb") as fh:
                self.assertNotIn(DEFAULT_PASSWORD.encode(), fh.read(), path)

    def test_same_password_gets_different_hashes(self):
        self.register("one@example.com")
        self.register("two@example.com")
        h1, h2 = [r["password_hash"] for r in self.sql("SELECT password_hash FROM users")]
        self.assertNotEqual(h1, h2)                              # unique salt per user

    def test_production_uses_scrypt(self):
        from app.config import ProductionConfig
        self.assertEqual(ProductionConfig.PASSWORD_HASH_METHOD, "scrypt")
