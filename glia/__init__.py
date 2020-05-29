"""
 _____ _ _
|   __| |_|___
|  |  | | | .'|
|_____|_|_|__,|

"""

import os, sys

__version__ = "0.2.1"


glia_path = os.path.dirname(__file__)
os.environ["GLIA_PATH"] = os.path.abspath(glia_path)
# Fix for PATH on Travis CI.
if os.getenv("CI") and os.getenv("TRAVIS"):
    sys.path.insert(0, "/usr/local/nrn/lib/python")
# Try importing neuron, if it fails, mark it as unavailable
try:
    import neuron

    os.environ["GLIA_NRN_AVAILABLE"] = "1"
except Exception as e:
    os.environ["GLIA_NRN_AVAILABLE"] = "0"


from .glia import Glia
from .exceptions import GliaError, ResolveError, TooManyMatchesError

# Initialize the manager
manager = Glia()

try:
    if not os.getenv("GLIA_NO_INSTALL"):
        if not manager._is_installed():
            manager._install_self()
        if os.getenv("GLIA_NRN_AVAILABLE") == "0":
            raise Exception("Cannot start Glia without NEURON installed.")
        else:
            manager.start(load_dll=not bool(os.getenv("GLIA_NO_AUTOLOAD_DLL")))
except GliaError as e:
    print("GLIA ERROR", e)
    exit(1)


def insert(section, asset, attributes=None, pkg=None, variant=None, x=0.5):
    """
        Insert a mechanism or point process into a Section.

        :param section: The section to insert the asset into.
        :type section: Section
        :param asset: The name of the asset. Will be resolved into a fully qualified NEURON name based on preferences, unless a fully qualified name is given.
        :type asset: string
        :param attributes: Attributes of the asset to set on the section/mechanism.
        :type attributes: dict
        :param pkg: Package preference. Overrides global & script preferences.
        :type pkg: string
        :param variant: Variant preference. Overrides global & script preferences.
        :type variant: string
        :param x: Position along the `section` to place the point process at. Does not apply to mechanisms.
        :type x: float
        :raises: LibraryError if the asset isn't found or was incorrectly marked as a point process.
    """
    return manager.insert(
        section, asset, attributes=attributes, pkg=pkg, variant=variant, x=x
    )


def resolve(asset, pkg=None, variant=None):
    return manager.resolver.resolve(asset, pkg=pkg, variant=variant)


def select(asset, pkg=None, variant=None):
    """
        Set script scope preferences for an asset.

        :param asset: Unresolved asset name.
        :type asset: string
        :param pkg: Name of the package to prefer.
        :type pkg: string
        :param variant: Name of the variant to prefer.
        :type variant: string
    """
    return manager.select(asset, pkg=pkg, variant=variant)


def compile():
    """
        Compile and test all mod files found in all Glia packages.
    """
    return manager.compile()


def context(assets=None, pkg=None, variant=None):
    """
        Creates a context that sets glia preferences during a `with` statement.
    """
    return manager.context(assets=assets, pkg=pkg, variant=variant)
