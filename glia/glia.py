import os, sys, pkg_resources, json, subprocess
from shutil import copy2 as copy_file
from .hash import get_directory_hash
from .exceptions import GliaError, CompileError, LibraryError
from .resolution import Resolver

class Glia:

    def __init__(self):
        self.entry_points = []
        self.discover_packages()
        self.resolver = Resolver(self)

    def discover_packages(self):
        self.packages = []
        for pkg_ptr in pkg_resources.iter_entry_points("glia.package"):
            advert = pkg_ptr.load()
            self.entry_points.append(advert)
            self.packages.append(advert.package())

    @staticmethod
    def path(*subfolders):
        return os.path.abspath(os.path.join(os.environ["GLIA_PATH"], *subfolders))

    def start(self):
        self.compile(check_cache=True)
        self.init_neuron()

    def init_neuron(self):
        if hasattr(self, "h"):
            return
        from neuron import h
        self.h = h
        self.load_neuron_dll()

    def compile(self, check_cache=False):
        if check_cache:
            if not self.is_cache_fresh():
                print("Glia packages modified, cache outdated.")
            else:
                return
        print("Glia is compiling.")
        cache_data = {"mod_hashes": {}}
        mod_dirs = []
        mod_files = []
        assets = []
        for pkg in self.packages:
            mod_path = self.get_mod_path(pkg)
            mod_dirs.append(mod_path)
            for mod in pkg.mods:
                assets.append((pkg, mod))
                mod_file = self.get_asset_mod_path(pkg, mod)
                mod_files.append(mod_file)
                print("Compiling asset:", mod_file)
            cache_data["mod_hashes"][pkg.path] = get_directory_hash(mod_path)
        self._compile(mod_files)
        print("\nCompilation complete!")
        print("Compiled assets:", ", ".join(list(set(map(lambda a: a[0].name + '.' + a[1].asset_name + '({})'.format(a[1].variant), assets)))))
        self.update_cache(cache_data)
        print("Updated cache.")

    def _compile(self, files):
        neuron_mod_path = self.get_neuron_mod_path()
        for file in files:
            copy_file(file, neuron_mod_path)
        if sys.platform == "win32":
            self._compile_windows(neuron_mod_path)
        elif sys.platform == "linux":
            self._compile_linux(neuron_mod_path)
        else:
            raise NotImplementedError("Only linux and win32 are supported. You are using " + sys.platform)

    def _compile_windows(self, neuron_mod_path):
        nrn_path = os.getenv('NEURONHOME')
        current_dir = os.getcwd()
        os.chdir(neuron_mod_path)
        cyg_path = nrn_path.replace(":\\","\\").replace("\\","/")
        process = subprocess.Popen([
            os.path.join(nrn_path, "mingw/usr/bin/sh"),
            os.path.join(nrn_path, "lib/mknrndll.sh"),
            os.path.join("/cygdrive/", cyg_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = process.communicate(input=b'\n')
        self._compiled = process.returncode == 0
        os.chdir(current_dir)
        if process.returncode != 0:
            raise CompileError(stderr.decode('UTF-8'))

    def _compile_linux(self, neuron_mod_path):
        current_dir = os.getcwd()
        os.chdir(neuron_mod_path)
        process = subprocess.Popen(["nrnivmodl"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = process.communicate()
        self._compiled = process.returncode == 0
        os.chdir(current_dir)
        if process.returncode != 0:
            raise CompileError(stderr.decode('UTF-8'))

    def install(self, command):
        subprocess.call([sys.executable, "-m", "pip", "install", command])

    def test_mechanism(self, mechanism):
        self.init_neuron()
        s = self.h.Section()
        try:
            self.insert_mechanism(s, mechanism)
        except ValueError as e:
            if str(e).find("argument not a density mechanism name") != -1:
                raise LibraryError(mechanism + " mechanism not found")
        print("Mechanism OK!")

    def insert_mechanism(self, section, asset, pkg=None, variant=None):
        self.init_neuron()
        if asset.startswith("_glia"):
            mod_name = asset
            print("Using given mechanism '{}'".format(mod_name))
        else:
            mod_name = self.resolver.resolve(asset, pkg, variant)
            print("Selection resolved to", mod_name)
        try:
            return section.insert(mod_name)
        except ValueError as e:
            if str(e).find("argument not a density mechanism name") != -1:
                raise LibraryError(mod_name + " mechanism not found")

    def select(self, asset_name, glbl=False, pkg=None, variant=None):
        return self.resolver.set_preference(asset_name, glbl=glbl, pkg=pkg, variant=variant)

    def load_neuron_dll(self):
        if sys.platform == 'win32':
            self.h.nrn_load_dll(Glia.path(".neuron", "mod", "libnrnmech.dll"))
        else:
            self.h.nrn_load_dll(Glia.path(".neuron", "mod", "x86_64", ".libs", "libnrnmech.so"))

    def is_cache_fresh(self):
        try:
            cache_data = self.read_cache()
            hashes = cache_data["mod_hashes"]
            for pkg in self.packages:
                if not pkg.path in hashes:
                    return False
                hash = get_directory_hash(os.path.join(pkg.path, "mod"))
                if hash != hashes[pkg.path]:
                    return False
            return True
        except FileNotFoundError as _:
            return False

    def _is_installed(self):
        return os.path.exists(Glia.path(".glia"))

    def _install_self(self):
        print("Please wait while Glia glues your neurons together...")
        self._mkdir(".glia")
        self.create_cache()
        self.create_preferences()
        self._mkdir(".neuron")
        self._mkdir(".neuron", "mod")
        self.compile()
        print("Glia installed.")

    def _mkdir(self, *subfolders, throw=False):
        try:
            os.mkdir(Glia.path(*subfolders))
        except OSError as _:
            if throw:
                raise

    def get_mod_path(self, pkg):
        return os.path.abspath(os.path.join(pkg.path, "mod"))

    def get_neuron_mod_path(self):
        return Glia.path(".neuron", "mod")

    def get_asset_full_name(self, mod):
        return "{}__{}__{}".format(mod.namespace, mod.asset_name, mod.variant)

    def get_asset_mod_path(self, pkg, mod):
        return os.path.abspath(os.path.join(
            self.get_mod_path(pkg),
             self.get_asset_full_name(mod) + ".mod"
        ))

    def read_storage(self, *path):
            return json.load(open(self.path(".glia", *path)))

    def write_storage(self, data, *path):
        json.dump(data, open(self.path(".glia", *path), "w"))

    def read_cache(self):
        try:
            return self.read_storage("cache")
        except FileNotFoundError as _:
            self.create_cache()

    def write_cache(self, cache_data):
        self.write_storage(cache_data, "cache")

    def update_cache(self, cache_data):
        cache = self.read_cache()
        cache.update(cache_data)
        self.write_cache(cache)

    def create_cache(self):
        empty_cache = {"mod_hashes": []}
        self.write_cache(empty_cache)

    def read_preferences(self):
        return self.read_storage("preferences")

    def write_preferences(self, preferences):
        self.write_storage(preferences, "preferences")

    def create_preferences(self):
        self.write_storage({}, "preferences")

    def list_assets(self):
        print("Assets:", ", ".join(map(lambda e: e.name + ' (' + str(len(e)) + ')' ,self.resolver.index.values())))
        print("Packages:", ", ".join(map(lambda p: p.name, self.packages)))
