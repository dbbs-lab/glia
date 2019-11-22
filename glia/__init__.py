import os

__version__ = "0.0.1a8"

glia_path = os.path.dirname(__file__)
os.environ["GLIA_PATH"] = os.path.abspath(glia_path)
try:
    import neuron
    os.environ["GLIA_NRN_AVAILABLE"] = "1"
except Exception as e:
    os.environ["GLIA_NRN_AVAILABLE"] = "0"


from .glia import Glia
from .exceptions import GliaError
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
