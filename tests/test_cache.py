import unittest
import sys
import os
import shutil
import time
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.cache import FileCache

class TestFileCache(unittest.TestCase):
    def setUp(self):
        # Create a temp cache dir for testing
        self.test_dir = Path(__file__).parent / "temp_cache"
        self.cache = FileCache(self.test_dir)

    def tearDown(self):
        # Clean up temp cache
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_cache_set_and_get(self):
        namespace = "test"
        params = {"key": "val"}
        value = {"result": "success"}

        # Get before set -> None
        self.assertIsNone(self.cache.get(namespace, params))

        # Set -> Get -> value
        self.cache.set(namespace, params, value, ttl=10)
        self.assertEqual(self.cache.get(namespace, params), value)

    def test_cache_expiry(self):
        namespace = "test"
        params = {"key": "val"}
        value = {"result": "success"}

        # Set with 1s TTL
        self.cache.set(namespace, params, value, ttl=1)
        self.assertEqual(self.cache.get(namespace, params), value)

        # Wait 1.1s and verify expired
        time.sleep(1.1)
        self.assertIsNone(self.cache.get(namespace, params))

    def test_cache_invalidate(self):
        namespace = "test"
        params = {"key": "val"}
        value = {"result": "success"}

        self.cache.set(namespace, params, value, ttl=10)
        self.assertEqual(self.cache.get(namespace, params), value)

        self.cache.invalidate(namespace, params)
        self.assertIsNone(self.cache.get(namespace, params))

if __name__ == "__main__":
    unittest.main()
