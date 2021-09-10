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
            any(["glia_test_mods" in hash for hash in cache["mod_hashes"].keys()])
        )


class TestCompilation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import glia

        glia.compile()

    def test_compilation(self):
        from glob import glob
        import glia

        path = glia._manager.get_neuron_mod_path()
        # Check that with `glia_test_mods` installed there are 3 mechanism folders
        self.assertEqual(len(glob(os.path.join(path, "*/"))), 3)
        # Check that all 3 libraries are picked up by `get_libraries`
        self.assertEqual(len(glia._manager.get_libraries()), 3)

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


class TestBuiltins(unittest.TestCase):
    def test_builtins(self):
        import glia
        from patch import p

        s = p.Section()
        glia.insert(s, "pas")
        nrn_pkg = None
        for pkg in glia._manager.packages:
            if pkg.name == "NEURON":
                nrn_pkg = pkg
                break
        else:
            self.fail("NEURON builtin package not found.")
        self.assertEqual(
            [m.asset_name for m in pkg.mods],
            ["extracellular", "fastpas", "hh", "k_ion", "na_ion", "pas"],
            "NEURON builtins incorrect",
        )
