import unittest
import uuid

from core.single_instance import SingleInstance


class SingleInstanceTestCase(unittest.TestCase):
    def test_only_one_instance_can_hold_the_mutex(self) -> None:
        name = f"Local\\ODIN-Test-{uuid.uuid4()}"
        first = SingleInstance(name)
        second = SingleInstance(name)
        third = SingleInstance(name)

        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.close()
            self.assertTrue(third.acquire())
        finally:
            first.close()
            second.close()
            third.close()


if __name__ == "__main__":
    unittest.main()
