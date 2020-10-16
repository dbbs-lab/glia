import os, sys, pkg_resources, json, subprocess
from shutil import copy2 as copy_file, rmtree as rmdir
from functools import wraps
from ._hash import get_directory_hash, hash_path
from .exceptions import *
from .resolution import Resolver
from .assets import Package, Mod
import requests
import appdirs

_install_dirs = appdirs.AppDirs(appname="Glia", appauthor="DBBS")
_installed = None


def _requires_install(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._is_installed():
            self._install_self()
        return func(self, *args, **kwargs)

    return wrapper


def _requires_library(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._loaded:
            self.load_library()
        return func(self, *args, **kwargs)

    return wrapper


class Glia:
    def __init__(self):
        from . import __version__

        self.version = __version__
        self._compiled = False
        self._loaded = False
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
    def get_glia_path():
        from . import __path__

        return __path__[0]

    @staticmethod
    def get_cache_hash():
        return hash_path(Glia.get_glia_path())[:8]

    @staticmethod
    def get_cache_path(*subfolders):
        return os.path.join(
            _install_dirs.user_cache_dir, Glia.get_cache_hash(), *subfolders
        )

    @staticmethod
    def get_data_path(*subfolders):
        return os.path.join(_install_dirs.user_data_dir, *subfolders)

    def start(self, load_dll=True):
        self.compile(check_cache=True)

    def get_minimum_astro_version(self):
        return "0.0.3"

    @_requires_install
    def load_library(self):
        if not self._compiled:
            self.compile(check_cache=True)
        if not self._loaded:
            self._add_neuron_pkg()
            self._load_neuron_dll()

    @_requires_install
    def compile(self, check_cache=False):
        """
            Compile and test all mod files found in all Glia packages.

            :param check_cache: If true, the cache is checked and compilation is only performed if it is stale.
            :type check_cache: boolean
        """
        self._compiled = True
        if not check_cache or not self.is_cache_fresh():
            self._compile()

    @_requires_install
    def _compile(self):
        assets, mod_files, cache_data = self._collect_asset_state()
        if len(mod_files) == 0:
            return
        # Walk over all files in the neuron mod path and remove them then copy over all
        # `mod_files` that have to be compiled. Afterwards run a platform specific
        # compile command.
        neuron_mod_path = self.get_neuron_mod_path()
        _remove_tree(neuron_mod_path)
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
        # Update the cache with the new mod directory hashes.
        self.update_cache(cache_data)

    def _compile_windows(self, neuron_mod_path):
        # Compile the glia cache for Linux.
        # Swap the python process's current working directory to the glia mod directory
        # and run mknrndll.sh in mingw. This approach works even when the PATH isn't set
        # properly by the installer.
        from patch import p

        nrn_path = p.neuronhome()
        current_dir = os.getcwd()
        os.chdir(neuron_mod_path)
        process = subprocess.Popen(
            [os.path.join(nrn_path, "bin", "nrnivmodl.bat")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process.communicate(input=b"\n")
        self._compilation_failed = process.returncode != 0
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

    def _collect_asset_state(self):
        cache_data = self.read_cache()
        mod_files = []
        assets = []
        # Iterate over all discovered packages to collect the mod files.
        for pkg in self.packages:
            mod_path = self.get_mod_path(pkg)
            for mod in pkg.mods:
                assets.append((pkg, mod))
                mod_file = mod.mod_path
                mod_files.append(mod_file)
            # Hash mod directories and their contents to update the cache data.
            cache_data["mod_hashes"][pkg.path] = get_directory_hash(mod_path)
        return assets, mod_files, cache_data

    def install(self, command):
        """
            Install a package from the Glia package index.

            :param command: Command string to be passed to pip install, including name of the package(s) to install.
            :type command: string.
        """
        subprocess.call(
            [sys.executable, "-m", "pip", "install", command,]
        )

    def uninstall(self, command):
        """
            Uninstall a Glia package.
            :param command: Command string to be passed to pip uninstall, including name of the package(s) to uninstall.
            :type command: string.
        """
        subprocess.call([sys.executable, "-m", "pip", "uninstall", command])

    @_requires_library
    def test_mechanism(self, mechanism):
        """
            Try to insert a mechanism in a Section to test its available in NEURON.

            :param mechanism: Fully qualified NEURON name of the mechanism.
            :type mechanism: string
            :returns: True if the test succeeds
            :rtype: boolean
            :raises: LibraryError if the mechanism can't be inserted.
        """
        try:
            s = self.h.Section()
            self.insert(s, mechanism)
        except ValueError as e:
            if str(e).find("argument not a density mechanism name") != -1:
                raise LibraryError(mechanism + " mechanism could not be inserted.")
            raise
        return True

    @_requires_library
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
        if attributes is None:
            attributes = {}
        if asset.startswith("glia"):
            mod_name = asset
        else:
            mod_name = self.resolver.resolve(asset, pkg=pkg, variant=variant)
        mod = self.resolver.lookup(mod_name)
        if mod.is_point_process:  # Insert point process
            try:
                # Create a point process
                point_process = getattr(self.h, mod_name)(section(x))
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
            for key, value in attributes.items():
                setattr(point_process, key, value)
            return point_process
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

    @_requires_install
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

    @_requires_install
    def context(self, assets=None, pkg=None, variant=None):
        return self.resolver.preference_context(assets=assets, pkg=pkg, variant=variant)

    @_requires_library
    def resolve(self, *args, **kwargs):
        """
            Resolve the given specifications applying all preferences and return the
            full name as it is known in the library to NEURON.

            :param asset_name: Short name of the asset
            :type asset_name: str
            :param pkg: Package specification for the asset
            :type pkg: str
            :param variant: Variant specification for the asset
            :type variant: str
        """
        return self.resolver.resolve(*args, **kwargs)

    def _load_neuron_dll(self):
        if not os.path.exists(self.get_library()):
            return
        elif not self._loaded:
            from patch import p

            self.h = p
            self._dll_result = self.h.nrn_load_dll(self.get_library())
            self._loaded = self._dll_result == 1.0
            if not self._loaded:
                raise NeuronError("Library could not be loaded into NEURON.")
        else:
            # If NEURON is asked to load a library that contains names that are imported
            # already it exits very ungracefully, waiting for user input and then killing
            # our process. See https://github.com/neuronsimulator/nrn/issues/570
            pass

    def get_library(self):
        """
            Return the location of the library (dll/so) to be loaded into NEURON. Or
            perhaps for use in dark neuroscientific rituals, who knows.
        """
        if sys.platform == "win32":
            path = ["nrnmech.dll"]
        else:
            path = ["x86_64", ".libs", "libnrnmech.so"]
        return Glia.get_cache_path(*path)

    def is_cache_fresh(self):
        try:
            cache_data = self.read_cache()
            hashes = cache_data["mod_hashes"]
            for pkg in self.packages:
                if pkg.path not in hashes:
                    return False
                hash = get_directory_hash(os.path.join(pkg.path, "mod"))
                if hash != hashes[pkg.path]:
                    return False
            return True
        except FileNotFoundError as _:
            return False

    def _is_installed(self):
        global _installed
        if _installed:
            return _installed
        _installed = os.path.exists(Glia.get_data_path()) and os.path.exists(
            Glia.get_cache_path()
        )
        return _installed

    def _install_self(self):
        try:
            os.makedirs(Glia.get_data_path())
        except FileExistsError:
            pass
        self.create_cache()
        self.create_preferences()
        try:
            os.makedirs(Glia.get_cache_path())
        except FileExistsError:
            pass
        self.resolver = Resolver(self)
        self.compile()

    def _add_neuron_pkg(self):
        import neuron
        from neuron import h

        nrn_pkg = Package("NEURON", neuron.__path__)
        builtin_mechs = []
        # Get all the builtin mechanisms by triggering a TypeError (NEURON 7.7 or below)
        # Or by it being a "DensityMechanism" (NEURON 7.8 or above)
        for k in dir(h):
            try:
                m = str(getattr(h, k))
                if "neuron.DensityMechanism" in m:
                    builtin_mechs.append(k)
            except TypeError as e:
                if "mechanism" in str(e):
                    builtin_mechs.append(k)
            except:
                pass

        for mech in builtin_mechs:
            mod = Mod(nrn_pkg, mech, 0, builtin=True)
            nrn_pkg.mods.append(mod)
        self.packages.append(nrn_pkg)
        if self.resolver:
            self.resolver.construct_index()

    def get_mod_path(self, pkg):
        return os.path.abspath(os.path.join(pkg.path, "mod"))

    def get_neuron_mod_path(self):
        return Glia.get_cache_path()

    def _read_shared_storage(self, *path):
        _path = Glia.get_data_path(*path)
        try:
            with open(_path, "r") as f:
                return json.load(f)
        except IOError:
            return {}

    def _write_shared_storage(self, data, *path):
        _path = Glia.get_data_path(*path)
        with open(_path, "w") as f:
            f.write(json.dumps(data))

    def read_storage(self, *path):
        data = self._read_shared_storage(*path)
        glia_path = Glia.get_glia_path()
        if glia_path not in data:
            return {}
        return data[glia_path]

    def write_storage(self, data, *path):
        _path = Glia.get_data_path(*path)
        glia_path = Glia.get_glia_path()
        shared_data = self._read_shared_storage(*path)
        shared_data[glia_path] = data
        self._write_shared_storage(shared_data, *path)

    def read_cache(self):
        cache = self.read_storage("cache.json")
        if "mod_hashes" not in cache:
            cache["mod_hashes"] = {}
        return cache

    def write_cache(self, cache_data):
        self.write_storage(cache_data, "cache.json")

    def update_cache(self, cache_data):
        cache = self.read_cache()
        cache.update(cache_data)
        self.write_cache(cache)

    def create_cache(self):
        empty_cache = {"mod_hashes": {}}
        self.write_cache(empty_cache)

    def read_preferences(self):
        return self.read_storage("preferences.json")

    def write_preferences(self, preferences):
        self.write_storage(preferences, "preferences.json")

    def create_preferences(self):
        self.write_storage({}, "preferences.json")

    @_requires_install
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


def _remove_tree(path):
    # Clear compiled mods
    for root, dirs, files in os.walk(path):
        for dir in dirs:
            try:
                rmdir(os.path.join(path, dir))
            except PermissionError as _:
                pass
        for file in files:
            try:
                os.remove(os.path.join(path, file))
            except PermissionError as _:
                print("Couldn't remove", file)
