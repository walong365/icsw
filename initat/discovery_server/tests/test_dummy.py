
import unittest
from django.test import TestCase


class DummyTest(TestCase):
    @unittest.skip("disabled")
    def test_a(self):
        self.assertTrue(False)

    def test_b(self):
        self.assertFalse(False)


if __name__ == '__main__':
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

    import django
    django.setup()

    unittest.main()