import sys
import unittest


@unittest.skipIf(sys.platform != "linux", "Arbor is Linux only.")
class TestCatalogues(unittest.TestCase):
    """
    Check if catalogues can be built.
    """

    def test_build(self):
        # todo: add catalogue to glia_test_mods, then try to build it here.
        pass
