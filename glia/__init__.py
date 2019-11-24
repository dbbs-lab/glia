import os, sys

__version__ = "0.1.2"



glia_path = os.path.dirname(__file__)
os.environ["GLIA_PATH"] = os.path.abspath(glia_path)
if os.getenv("CI") and os.getenv("TRAVIS"):
    sys.path.insert(0, "/usr/local/nrn/lib/python")
try:
    import neuron
    os.environ["GLIA_NRN_AVAILABLE"] = "1"
except Exception as e:
    os.environ["GLIA_NRN_AVAILABLE"] = "0"


from .glia import Glia
from .exceptions import GliaError, ResolveError, TooManyMatchesError
manager = Glia()

try:
    if not os.getenv("GLIA_NO_INSTALL"):
        if not manager._is_installed():
            manager._install_self()
        if os.getenv("GLIA_NRN_AVAILABLE") == "0":
            raise Exception("Cannot start Glia without NEURON installed.")
        else:
            manager.start()
except GliaError as e:
    print("GLIA ERROR", e)
    exit(1)

def insert(section, asset, pkg=None, variant=None):
    return manager.insert_mechanism(section, asset, pkg, variant)

def resolve(asset, pkg=None, variant=None):
    return manager.resolver.resolve(asset, pkg, variant)

def select(asset, pkg=None, variant=None):
    return manager.select(asset, pkg=pkg, variant=variant)

def compile():
    return manager.compile()
