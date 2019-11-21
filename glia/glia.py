import os

class Glia:

    @staticmethod
    def path(*subfolders):
        return os.path.join(os.environ["GLIA_PATH"], *subfolders)

    def start(self):
        if not self.is_cache_fresh():
            self.compile()
        from neuron import h
        h.nrn_load_dll(Glia.path(".neuron", "x86_64", ".libs", "libnrnmech.so"))

    def compile(self):
        print("Glia is compiling.")

    def install(self, package):
        pass

    def is_cache_fresh(self):
        return True

    def _is_installed(self):
        return os.path.exists(Glia.path(".glia"))

    def _install_self(self):
        print("Please wait while Glia glues your neurons together...")
        self._mkdir(".glia")
        self._mkdir(".neuron")
        self._mkdir(".neuron", "mod")
        print("Glia installed.")

    def _mkdir(self, *subfolders, throw=False):
        try:
            os.mkdir(Glia.path(*subfolders))
        except OSError as _:
            if throw:
                raise
