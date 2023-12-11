import os
import unittest

from patch import p

import glia._glia
from glia._fs import read_cache
from tests._shared import skipUnlessTestMods


@skipUnlessTestMods
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
        glia.compile()

    def test_compilation(self):
        # Check that the library files exist
        for path in glia._manager.get_libraries():
            with self.subTest(path=path):
                self.assertTrue(os.path.exists(path), "Missing library file")

    @skipUnlessTestMods
    def test_insert(self):
        # Test mechanism insertion
        mech = glia._manager.insert(p.Section(), "Na")
        self.assertIsInstance(mech, glia._glia.MechAccessor)
        self.assertTrue(glia._manager.test_mechanism("AMPA"))
        self.assertTrue(glia._manager.test_mechanism("Na"))

    @skipUnlessTestMods
    def test_insert_attrs(self):
        # Test mechanism attributes
        sec = p.Section()
        mech = glia._manager.insert(sec, "Na", attributes={"gnabar": 30})
        self.assertEqual(30, mech.get_parameter("gnabar"), "Attribute not set")
        self.assertRaises(
            AttributeError,
            glia._manager.insert,
            p.Section(),
            "Na",
            attributes={"doesntexist": 30},
        )

    @skipUnlessTestMods
    def test_insert_pp(self):
        # Test point process insertion
        pp = glia._manager.insert(p.Section(), "AMPA")
        self.assertIsInstance(pp, glia._glia.MechAccessor)

    @skipUnlessTestMods
    def test_insert_pp_attrs(self):
        glia._manager.insert(p.Section(), "AMPA", attributes={"U": 30})
        self.assertRaises(
            AttributeError,
            glia._manager.insert,
            p.Section(),
            "AMPA",
            attributes={"doesntexist": 30},
        )


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
