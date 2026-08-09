import unittest

from core.config import Config


class InaraConfigTests(unittest.TestCase):
    @staticmethod
    def config(data):
        config=Config.__new__(Config); config.data=data; return config

    def test_private_capture_and_upload_are_disabled_by_default(self):
        config=self.config({})
        self.assertFalse(config.inara_capture_enabled)
        self.assertFalse(config.inara_upload_enabled)

    def test_capture_and_upload_are_independent(self):
        config=self.config({"inara_capture_enabled":False,"inara_upload_enabled":True})
        self.assertFalse(config.inara_capture_enabled)
        self.assertTrue(config.inara_upload_enabled)


if __name__=="__main__": unittest.main()
