import unittest, os, sys, importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPackageDiscovery(unittest.TestCase):
    """
        Check if packages can be discovered.
    """

    def test_discovery(self):
        import glia

        self.assertGreater(len(glia._manager.packages), 0)

    def test_caching(self):
        import glia

        cache = glia._manager.read_cache()
        # Check whether the directory hash for `glia_test_mods` is present.
        self.assertTrue(
            any([h.find("glia_test_mods") != -1 for h in cache["mod_hashes"].keys()])
        )

    def test_compilation(self):
        import glia
        from glob import glob

        path = glia._manager.get_neuron_mod_path()
        self.assertEqual(len(glob(os.path.join(path, "*.mod"))), 3)
        self.assertEqual(len(glob(glia._manager.get_library())), 1)

    def test_insert(self):
        from patch import p
        import patch.objects
        import glia as g

        # Test mechanism insertion
        self.assertEqual(type(g.insert(p.Section(), "cdp5")), patch.objects.Section)
        self.assertTrue(g._manager.test_mechanism("cdp5"))
        self.assertTrue(g._manager.test_mechanism("Kir2_3"))

        # Test mechanism attributes
        g._manager.insert(p.Section(), "Kir2_3", attributes={"gkbar": 30})
        self.assertRaises(
            AttributeError,
            g._manager.insert,
            p.Section(),
            "Kir2_3",
            attributes={"doesntexist": 30},
        )

        # TODO: Test point process insertion
        # TODO: Test point process attribute setting
