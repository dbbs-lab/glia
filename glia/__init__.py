import os
glia_path = os.path.dirname(__file__)
os.environ["GLIA_PATH"] = glia_path
try:
    import neuron
    os.environ["GLIA_NRN_AVAILABLE"] = "1"
except Exception as e:
    os.environ["GLIA_NRN_AVAILABLE"] = "0"


from .glia import Glia
manager = Glia()

if not manager._is_installed():
    manager._install_self()

if os.getenv("GLIA_NRN_AVAILABLE") == "0":
    raise Exception("Cannot start Glia without NEURON installed.")
else:
    manager.start()
