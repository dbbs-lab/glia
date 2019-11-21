import os, warnings
glia_path = os.path.dirname(__file__)
os.environ["GLIA_PATH"] = glia_path
from .glia import Glia

glia = Glia()

try:
    import neuron
except Exception as e:
    raise Exception("Could not load neuron.") from None

if not os.path.exists(Glia.path(".glia")):
    print("No install found.")
    glia.install()
else:
    print("Glia installed")
