import unittest, os, sys, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import glia._cli

# Duck punch the argument parser so it doesn't sys.exit
def on_argparse_error(self, message):
    raise argparse.ArgumentError(None, message)


argparse.ArgumentParser.error = on_argparse_error


def run_cli_command(command):
    argv = sys.argv
    sys.argv = command.split(" ")
    sys.argv.insert(0, "test_cli_command")
    result = glia._cli.glia_cli()
    sys.argv = argv
    return result


class TestCLI(unittest.TestCase):
    """
    Check if packages can be discovered.
    """

    def test_basics(self):
        self.assertRaises(argparse.ArgumentError, run_cli_command, "doesntexist")

    def test_compile(self):
        run_cli_command("compile")

    def test_pkg_install(self):
        run_cli_command("list")

    def test_show(self):
        run_cli_command("show Kir2_3")
        run_cli_command("show-pkg glia_test_mods")
