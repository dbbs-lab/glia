import os, sys

__version__ = "4.0.0a4"

from ._glia import Glia
from .exceptions import *

# Initialize the manager
_manager = Glia()


def insert(section, asset, variant=None, pkg=None, /, attributes=None, x=None):
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
    return _manager.insert(section, asset, variant, pkg, attributes, x)


def resolve(asset, pkg=None, variant=None):
    """
    Resolve an asset selection command to the name known to NEURON.
    """
    return _manager.resolve(asset, pkg=pkg, variant=variant)


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
    return _manager.select(asset, pkg=pkg, variant=variant)


def compile():
    """
    Compile and test all mod files found in all Glia packages.
    """
    return _manager.compile()


def load_library():
    """
    Load the glia library (if it isn't loaded yet).
    """
    return _manager.load_library()


def context(assets=None, pkg=None, variant=None):
    """
    Creates a context that sets glia preferences during a `with` statement.
    """
    return _manager.context(assets=assets, pkg=pkg, variant=variant)


def catalogue(name):
    """
    Load or build an Arbor mechanism catalogue.

    :param name: Name of the Glia installed Arbor catalogue.
    :type name: str
    """
    return _manager.catalogue(name)


def package(name):
    """
    Return package.

    :param name: Name of the installed glia package.
    :type name: str
    """
    return _manager.package(name)
