import unittest
from pathlib import Path


class DistributionProfileTests(unittest.TestCase):
    def test_main_distribution_does_not_disable_brokk(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / "ODIN.spec").read_text(encoding="utf-8")
        self.assertNotIn('runtime_hooks=[str(root / "installer" / "runtime_pre_brokk.py")]', spec)
        self.assertIn("runtime_hooks=[]", spec)

    def test_public_pre_ai_distribution_explicitly_enables_brokk(self):
        root = Path(__file__).resolve().parents[1]
        hook = (root / "installer" / "runtime_public_no_ai.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('os.environ["ODIN_ENABLE_BROKK"] = "1"', hook)


if __name__ == "__main__":
    unittest.main()
