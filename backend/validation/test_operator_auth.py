"""Single operator credential: hashing, verification and the login route."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import app
from operator_auth import hash_password, verify_operator

ENV={'OPERATOR_USERNAME':'operator','OPERATOR_PASSWORD_HASH':hash_password('correct horse',iterations=1000)}


class VerifyOperatorTests(unittest.TestCase):
    def test_correct_credentials(self):
        self.assertTrue(verify_operator('operator','correct horse',ENV))

    def test_wrong_password_or_username(self):
        self.assertFalse(verify_operator('operator','wrong',ENV))
        self.assertFalse(verify_operator('driver','correct horse',ENV))

    def test_hash_is_salted(self):
        self.assertNotEqual(hash_password('same',iterations=1000),hash_password('same',iterations=1000))

    def test_missing_or_malformed_configuration_raises(self):
        for env in ({},{'OPERATOR_USERNAME':'operator'},
                    {'OPERATOR_USERNAME':'operator','OPERATOR_PASSWORD_HASH':'plain-text'},
                    {'OPERATOR_USERNAME':'operator','OPERATOR_PASSWORD_HASH':'md5$1$00$ab'}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                verify_operator('operator','correct horse',env)


class OperatorLoginRouteTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app)

    def test_route_statuses(self):
        with patch.dict('os.environ',ENV):
            self.assertEqual(self.client.post('/operator/login',json={'username':'operator','password':'correct horse'}).status_code,200)
            self.assertEqual(self.client.post('/operator/login',json={'username':'operator','password':'nope'}).status_code,401)
        with patch.dict('os.environ',{'OPERATOR_USERNAME':'','OPERATOR_PASSWORD_HASH':''}):
            self.assertEqual(self.client.post('/operator/login',json={'username':'operator','password':'x'}).status_code,503)
        self.assertEqual(self.client.post('/operator/login',json={'username':'','password':'x'}).status_code,422)


if __name__=='__main__':
    unittest.main()
