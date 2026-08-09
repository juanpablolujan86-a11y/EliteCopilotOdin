import unittest

from core.config import Config


class EDDNConfigTests(unittest.TestCase):
    @staticmethod
    def config(data):
        config=Config.__new__(Config)
        config.data=data
        return config

    def test_all_network_features_are_safe_by_default(self):
        config=self.config({})
        self.assertFalse(config.eddn_capture_enabled)
        self.assertFalse(config.eddn_upload_enabled)
        self.assertTrue(config.eddn_test_mode)

    def test_live_mode_requires_explicit_false_value(self):
        self.assertFalse(self.config({"eddn_test_mode":False}).eddn_test_mode)
        self.assertFalse(self.config({"eddn_test_mode":"false"}).eddn_test_mode)
        self.assertTrue(self.config({"eddn_test_mode":"true"}).eddn_test_mode)


if __name__=="__main__": unittest.main()
