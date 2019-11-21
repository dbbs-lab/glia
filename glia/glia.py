import os

class Glia:

    @staticmethod
    def path(*subfolders):
        return os.path.join(os.environ["GLIA_PATH"], *subfolders)

    def install(self):
        os.mkdir(Glia.path(".glia"))
        os.mkdir(Glia.path(".neuron"))
