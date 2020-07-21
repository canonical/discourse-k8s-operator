import unittest

import sys

sys.path.append('src')  # noqa: E402

from charm import create_ingress_config


class TestDiscourseCharm(unittest.TestCase):
    def test_create_ingress_config(self):
        config = {
            "external_hostname": "testhost",
        }
        expected = {
            "name": "test-app-ingress",
            "spec": {
                "rules": [
                    {
                        "host": "testhost",
                        "http": {"paths": [{"path": "/", "backend": {"serviceName": "test-app", "servicePort": 3000}}]},
                    }
                ]
            },
        }
        self.assertEqual(create_ingress_config("test-app", config), expected)
