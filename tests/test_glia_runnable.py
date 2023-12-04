import importlib.util
import os
import unittest

import glia._glia
from glia._fs import read_cache


@unittest.skipIf(
    not importlib.util.find_spec("glia_test_mods"),
    "Package discovery should be tested with the `glia_test_mods` package installed.",
)
class TestPackageDiscovery(unittest.TestCase):
    """
    Check if packages can be discovered.
    """

    def test_discovery(self):
        self.assertGreater(len(glia._manager.packages), 0)

    def test_caching(self):
        cache = read_cache()
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
        import glia

        # Check that the library files exist
        for path in glia._manager.get_libraries():
            with self.subTest(path=path):
                self.assertTrue(os.path.exists(path), "Missing library file")

    def test_insert(self):
        from patch import p

        import glia as g

        # Test mechanism insertion
        self.assertEqual(type(g.insert(p.Section(), "cdp5")), glia._glia.MechAccessor)
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
        from patch import p

        import glia

        s = p.Section()
        glia.insert(s, "pas")
        for pkg in glia._manager.packages:
            if pkg.name == "NEURON":
                nrn_pkg = pkg
                break
        else:
            self.fail("NEURON builtin package not found.")
        self.assertEqual(
            [m.asset_name for m in nrn_pkg.mods],
            [
                "APCount",
                "AlphaSynapse",
                "Exp2Syn",
                "ExpSyn",
                "IClamp",
                "OClamp",
                "PointProcessMark",
                "SEClamp",
                "VClamp",
                "extracellular",
                "fastpas",
                "hh",
                "k_ion",
                "na_ion",
                "pas",
            ],
            "NEURON builtins incorrect",
        )
