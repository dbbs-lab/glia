import argparse
import sys
import unittest

import glia._cli
import glia._mpi


# Duck punch the argument parser so it doesn't sys.exit
def on_argparse_error(self, message):
    raise argparse.ArgumentError(None, message)


argparse.ArgumentParser.error = on_argparse_error


def run_cli_command(command):
    argv = sys.argv
    sys.argv = command.split(" ")
    sys.argv.insert(0, "test_cli_command")
    try:
        result = glia._cli.glia_cli()
    finally:
        sys.argv = argv
    return result


class TestCLI(unittest.TestCase):
    """
    Check if packages can be discovered.
    """

    def test_basics(self):
        self.assertRaises(argparse.ArgumentError, run_cli_command, "doesntexist")

    @unittest.skipIf(glia._mpi.parallel_run, "Skip in parallel")
    def test_compile(self):
        run_cli_command("compile")

    def test_pkg_install(self):
        run_cli_command("list")

    def test_show(self):
        run_cli_command("show Kir2_3")
        run_cli_command("show-pkg glia_test_mods")
