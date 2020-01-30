import os, sys, pkg_resources, json, subprocess
from shutil import copy2 as copy_file, rmtree as rmdir
from .hash import get_directory_hash
from .exceptions import *
from .resolution import Resolver
from .assets import Package, Mod
import requests


class Glia:
    def __init__(self):
        from . import __version__

        self.version = __version__
        self.entry_points = []
        self.discover_packages()
        if self._is_installed():
            self.resolver = Resolver(self)
        else:
            self.resolver = None

    def discover_packages(self):
        self.packages = []
        for pkg_ptr in pkg_resources.iter_entry_points("glia.package"):
            advert = pkg_ptr.load()
            self.entry_points.append(advert)
            self.packages.append(Package.from_remote(self, advert))

    @staticmethod
    def path(*subfolders):
        return os.path.abspath(os.path.join(os.environ["GLIA_PATH"], *subfolders))

    def start(self, load_dll=True):
        self.compile(check_cache=True)
        self.init_neuron(load_dll=load_dll)

    def init_neuron(self, load_dll=True):
        if hasattr(self, "h"):
            return
        from patch import p

        self.h = p
        if load_dll:
            self.load_neuron_dll()

    def get_minimum_astro_version(self):
        return "0.0.3"

    def compile(self, check_cache=False):
        """
            Compile and test all mod files found in all Glia packages.

            :param check_cache: If true, the cache is checked and compilation is only performed if it is stale.
            :type check_cache: boolean
        """
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
        # Iterate over all discovered packages to collect the mod files.
        for pkg in self.packages:
            mod_path = self.get_mod_path(pkg)
            mod_dirs.append(mod_path)
            for mod in pkg.mods:
                assets.append((pkg, mod))
                mod_file = mod.mod_path
                mod_files.append(mod_file)
                print("Compiling asset:", mod_file)
            # Hash mod directories and their contents to update the cache data.
            cache_data["mod_hashes"][pkg.path] = get_directory_hash(mod_path)
        if len(mod_files) == 0:
            print(
                "No packages detected, compilation aborted. Install packages with `glia install`"
            )
            self._compiled = False
            return
        self._compile(mod_files)
        print("\nCompilation complete!")
        print(
            "Compiled assets:",
            ", ".join(
                list(
                    set(
                        map(
                            lambda a: a[0].name
                            + "."
                            + a[1].asset_name
                            + "({})".format(a[1].variant),
                            assets,
                        )
                    )
                )
            ),
        )
        # Update the cache with the new mod directory hashes.
        self.update_cache(cache_data)
        print("Updated cache.")
        print("Testing assets:")
        from .cli import test

        # Run an insertion test for each mechanism.
        if os.getenv("GLIA_NRN_AVAILABLE") == "1":
            test(*self.resolver.index.keys())

    def _compile(self, mod_files):
        # Walk over all files in the neuron mod path and remove them then copy over all
        # `mod_files` that have to be compiled. Afterwards run a platform specific
        # compile command.
        neuron_mod_path = self.get_neuron_mod_path()
        # Clear compiled mods
        for root, dirs, files in os.walk(neuron_mod_path):
            for dir in dirs:
                try:
                    rmdir(os.path.join(neuron_mod_path, dir))
                except PermissionError as _:
                    pass
            for file in files:
                try:
                    os.remove(os.path.join(neuron_mod_path, file))
                except PermissionError as _:
                    print("Couldn't remove", file)
        # Copy over fresh mods
        for file in mod_files:
            copy_file(file, neuron_mod_path)
        # Platform specific compile
        if sys.platform == "win32":
            self._compile_windows(neuron_mod_path)
        elif sys.platform == "linux":
            self._compile_linux(neuron_mod_path)
        else:
            raise NotImplementedError(
                "Only linux and win32 are supported. You are using " + sys.platform
            )

    def _compile_windows(self, neuron_mod_path):
        # Compile the glia cache for Linux.
        # Swap the python process's current working directory to the glia mod directory
        # and run mknrndll.sh in mingw. This approach works even when the PATH isn't set
        # properly by the installer.
        from patch import p

        nrn_path = p.neuronhome()
        current_dir = os.getcwd()
        os.chdir(neuron_mod_path)
        cyg_path = nrn_path.replace(":\\", "\\").replace("\\", "/")
        process = subprocess.Popen(
            [
                os.path.join(nrn_path, "mingw/usr/bin/sh"),
                os.path.join(nrn_path, "lib/mknrndll.sh"),
                os.path.join("/cygdrive/", cyg_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process.communicate(input=b"\n")
        self._compiled = process.returncode == 0
        os.chdir(current_dir)
        if process.returncode != 0:
            raise CompileError(stderr.decode("UTF-8"))

    def _compile_linux(self, neuron_mod_path):
        # Compile the glia cache for Linux.
        # Swap the python process's current working directory to the glia mod directory
        # and run nrnivmodl.
        current_dir = os.getcwd()
        os.chdir(neuron_mod_path)
        process = subprocess.Popen(
            ["nrnivmodl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process.communicate()
        self._compiled = process.returncode == 0
        os.chdir(current_dir)
        if process.returncode != 0:
            raise CompileError(stderr.decode("UTF-8"))

    def install(self, command):
        """
            Install a package from the Glia package index.

            :param command: Command string to be passed to pip install, including name of the package(s) to install.
            :type command: string.
        """
        subprocess.call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--index-url=https://pi.glia-pkg.org/",
                command,
            ]
        )

    def uninstall(self, command):
        """
            Uninstall a Glia package.
            :param command: Command string to be passed to pip uninstall, including name of the package(s) to uninstall.
            :type command: string.
        """
        subprocess.call([sys.executable, "-m", "pip", "uninstall", command])

    def test_mechanism(self, mechanism):
        """
            Try to insert a mechanism in a Section to test its available in NEURON.

            :param mechanism: Fully qualified NEURON name of the mechanism.
            :type mechanism: string
            :returns: True if the test succeeds
            :rtype: boolean
            :raises: LibraryError if the mechanism can't be inserted.
        """
        self.init_neuron()
        try:
            s = self.h.Section()
            self.insert(s, mechanism)
        except ValueError as e:
            if str(e).find("argument not a density mechanism name") != -1:
                raise LibraryError(mechanism + " mechanism could not be inserted.")
        return True

    def insert(self, section, asset, attributes=None, pkg=None, variant=None, x=0.5):
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
        # Transform the given section into a NEURON section.
        nrn_section = _transform(section)
        self.init_neuron()
        if attributes is None:
            attributes = {}
        if asset.startswith("glia"):
            mod_name = asset
        else:
            mod_name = self.resolver.resolve(asset, pkg=pkg, variant=variant)
        mod = self.resolver.lookup(mod_name)
        if mod.is_point_process:  # Insert point process
            try:
                # Get the point process factory from the hoc interpreter
                point_process_factory = getattr(self.h, mod_name)
                # Create a point process
                point_process = self.h.PointProcess(point_process_factory, nrn_section(x))
                for key, value in attributes.items():
                    setattr(point_process, key, value)
                return point_process
            except AttributeError as e:
                raise LibraryError(
                    "'{}' point process not found ".format(mod_name)
                ) from None
            except TypeError as e:
                if str(e).find("'dict_keys' object is not subscriptable") == -1:
                    raise
                else:
                    raise LibraryError(
                        "'{}' is marked as a point process, but isn't a point process in the NEURON library".format(
                            mod_name
                        )
                    ) from None
        else:  # Insert mechanism
            try:
                r = section.insert(mod_name)
                for attribute, value in attributes.items():
                    setattr(nrn_section, attribute + "_" + mod_name, value)
                return r
            except ValueError as e:
                if str(e).find("argument not a density mechanism name") != -1:
                    raise LibraryError(
                        "'{}' mechanism not found".format(mod_name)
                    ) from None

    def select(self, asset_name, glbl=False, pkg=None, variant=None):
        """
            Set script or global scope preferences for an asset.

            :param asset_name: Unresolved asset name.
            :type asset_name: string
            :param glbl: Set global scope instead of script scope.
            :type glbl: boolean
            :param pkg: Name of the package to prefer.
            :type pkg: string
            :param variant: Name of the variant to prefer.
            :type variant: string
        """
        return self.resolver.set_preference(
            asset_name, glbl=glbl, pkg=pkg, variant=variant
        )

    def context(self, assets=None, pkg=None, variant=None):
        return self.resolver.preference_context(assets=assets, pkg=pkg, variant=variant)

    def load_neuron_dll(self):
        if not hasattr(self, "_dll_result") or not self._dll_loaded:
            self._dll_result = self.h.nrn_load_dll(self.get_neuron_dll())
            self._dll_loaded = self._dll_result == 1.0
            if not self._dll_loaded:
                raise NeuronError("Library could not be loaded into NEURON.")
        else:
            print("NEURON DLL already succesfully loaded.")

    def get_neuron_dll(self):
        if sys.platform == "win32":
            return Glia.path(".neuron", "mod", "nrnmech.dll")
        else:
            return Glia.path(".neuron", "mod", "x86_64", ".libs", "libnrnmech.so")

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
        self.resolver = Resolver(self)
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

    def read_storage(self, *path):
        with open(self.path(".glia", *path)) as f:
            return json.load(f)

    def write_storage(self, data, *path):
        with open(self.path(".glia", *path), "w") as f:
            json.dump(data, f)

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
        print(
            "Assets:",
            ", ".join(
                map(
                    lambda e: e.name + " (" + str(len(e)) + ")",
                    self.resolver.index.values(),
                )
            ),
        )
        print("Packages:", ", ".join(map(lambda p: p.name, self.packages)))


def _transform(obj):
    # Transform an object to its NEURON counterpart, if possible, otherwise
    # return the object itself.

    # Does the given object expose a method to convert it into a  NEURON representation?
    if hasattr(obj, "__neuron__"):
        # Transform the given object into its NEURON representation.
        obj = obj.__neuron__()
    return obj
