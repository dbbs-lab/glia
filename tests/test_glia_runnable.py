import unittest, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def execute_command(cmnd):
    import subprocess

    process = subprocess.Popen(cmnd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out_str, std_err_str = "", ""
    for c in iter(lambda: process.stdout.read(1), b""):
        s = c.decode("UTF-8")
        sys.stdout.write(s)
        std_out_str += s
    for c in iter(lambda: process.stderr.read(1), b""):
        s = c.decode("UTF-8")
        std_err_str += s
    return process, std_out_str, std_err_str


class TestPackageDiscovery(unittest.TestCase):
    """
        Check if packages can be discovered.
    """

    @classmethod
    def setUpClass(self):
        process, _, _ = execute_command(["pip3", "install", "glia_test_mods"])
        process.communicate()

    @classmethod
    def tearDownClass(self):
        process, _, _ = execute_command(["pip3", "uninstall", "glia_test_mods", "-y"])
        process.communicate()

    def test_discovery(self):
        import glia

        self.assertGreater(len(glia.manager.packages), 0)

    def test_caching(self):
        import glia

        cache = glia.manager.read_cache()
        # Check whether the directory hash for `glia_test_mods` is present.
        self.assertTrue(
            any([h.find("glia_test_mods") != -1 for h in cache["mod_hashes"].keys()])
        )

    def test_compilation(self):
        import glia
        from glob import glob

        path = glia.manager.get_neuron_mod_path()
        self.assertEqual(len(glob(os.path.join(path, "*.mod"))), 2)
        self.assertEqual(len(glob(glia.manager.get_neuron_dll())), 1)

    def test_insert(self):
        from patch import p
        import glia as g

        # Test mechanism insertion
        self.assertTrue(g.manager.test_mechanism("cdp5_CR"))
        self.assertTrue(g.manager.test_mechanism("Kir23"))

        # Test mechanism attributes
        g.manager.insert(p.Section(), "Kir23", attributes={"gkbar": 30})
        self.assertRaises(
            AttributeError,
            g.manager.insert,
            p.Section(),
            "Kir23",
            attributes={"doesntexist": 30},
        )

        # TODO: Test point process insertion
        # TODO: Test point process attribute setting
