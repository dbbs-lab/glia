import os, sys, pkg_resources, json, subprocess
import weakref
from shutil import copy2 as copy_file, rmtree as rmdir
from functools import wraps
from ._hash import get_directory_hash, hash_path
from .exceptions import (
    CatalogueError,
    LibraryError,
    CompileError,
    NeuronError,
    PackageError,
)
from .resolution import Resolver
import appdirs
from glob import glob

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


def _should_skip_compile():
    return os.environ.get("GLIA_NOCOMPILE", "").upper() in ("1", "TRUE", "ON")


def _should_skip_load():
    return os.environ.get("GLIA_NOLOAD", "").upper() in ("1", "TRUE", "ON")


class Glia:
    def __init__(self):
        from . import __version__

        self.version = __version__
        self._compiled = False
        self._loaded = False
        self.entry_points = []
        self._packages = None
        self._catalogues = None
        self._resolver = None

    @property
    def resolver(self):
        if self._resolver is None and self._is_installed():
            self._resolver = Resolver(self)
        return self._resolver

    @property
    def packages(self):
        if self._packages is None:
            self.discover_packages()
        return self._packages

    @property
    def catalogues(self):
        if self._catalogues is None:
            self.discover_catalogues()
        return self._catalogues

    def discover_packages(self):
        from .assets import Package

        self._packages = []
        for pkg_ptr in pkg_resources.iter_entry_points("glia.package"):
            advert = pkg_ptr.load()
            self.entry_points.append(advert)
            self._packages.append(Package.from_remote(self, advert))

    def discover_catalogues(self):
        self._catalogues = {}
        for pkg_ptr in pkg_resources.iter_entry_points("glia.catalogue"):
            advert = pkg_ptr.load()
            self.entry_points.append(advert)
            if advert.name in self._catalogues:
                raise RuntimeError(
                    f"Duplicate installations of `{advert.name}` catalogue:"
                    + f"\n{self._catalogues[advert.name].path}"
                    + f"\n{advert.path}"
                )
            self._catalogues[advert.name] = advert

    def _get_catalogue(self, name):
        try:
            cat = self.catalogues[name]
        except KeyError:
            raise CatalogueError(f"Catalogue '{name}' not found.") from None
        else:
            return cat

    @_requires_install
    def catalogue(self, name):
        return self._get_catalogue(name).load()

    @_requires_install
    def build_catalogue(self, name, debug=False, verbose=False, gpu=None):
        return self._get_catalogue(name).build(verbose=verbose, debug=debug, gpu=gpu)

    @staticmethod
    def get_glia_path():
        from . import __path__

        return __path__[0]

    @staticmethod
    def get_cache_hash(for_arbor=False):
        cache_slug = hash_path(Glia.get_glia_path())[:8]
        if for_arbor:
            cache_slug = "arb_" + cache_slug
        return cache_slug

    @staticmethod
    def get_cache_path(*subfolders, for_arbor=False):
        return os.path.join(
            _install_dirs.user_cache_dir,
            Glia.get_cache_hash(for_arbor=for_arbor),
            *subfolders,
        )

    @staticmethod
    def get_data_path(*subfolders):
        return os.path.join(_install_dirs.user_data_dir, *subfolders)

    def start(self, load_dll=True):
        self.compile(check_cache=True)

    def get_minimum_astro_version(self):
        return "0.0.3"

    @_requires_install
    def package(self, name):
        for pkg in self.packages:
            if pkg.name == name:
                return pkg
        else:
            raise PackageError(f"Package '{name}' not found.")

    @_requires_install
    def load_library(self):
        if not self._compiled:
            self.compile(check_cache=True)
        if not self._loaded:
            self._add_neuron_pkg()
            self._load_all_libraries()

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
        if _should_skip_compile():
            return self.update_cache(cache_data)
        if len(mod_files) == 0:
            return
        for i in self._distribute_n(len(mod_files)):
            self._compile_nrn_mod(assets[i], mod_files[i])
        # Update the cache with the new mod directory hashes.
        self.update_cache(cache_data)

    def _compile_nrn_mod(self, asset, file):
        mod_path = self.get_neuron_mod_path(asset[1].mod_name)
        os.makedirs(mod_path, exist_ok=True)
        # Clean out previous files inside of the mod path
        _remove_tree(mod_path)
        # Copy over the mod file
        copy_file(file, mod_path)
        # Platform specific compile
        if sys.platform == "win32":
            self._compile_nrn_windows(mod_path)
        elif sys.platform in ("linux", "darwin"):
            self._compile_nrn_linux(mod_path)
        else:
            raise NotImplementedError(
                "Only linux, darwin and win32 are supported. You are using "
                + sys.platform
            )

    def _distribute_n(self, n):
        try:
            from mpi4py.MPI import COMM_WORLD
        except ImportError:
            return range(0, n)
        else:
            r = COMM_WORLD.Get_rank()
            s = COMM_WORLD.Get_size()
            return range(r, n, s)

    def _compile_nrn_windows(self, neuron_mod_path):
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

    def _compile_nrn_linux(self, neuron_mod_path):
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
        cache_data = Glia.read_cache()
        mod_files = []
        assets = []
        # Iterate over all discovered packages to collect the mod files.
        for pkg in self.packages:
            if pkg.builtin:
                continue
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
            [
                sys.executable,
                "-m",
                "pip",
                "install",
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
    def insert(self, section, asset, variant=None, pkg=None, /, attributes=None, x=None):
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
            x = x if x is not None else 0.5
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
                        f"'{mod_name}' is marked as a point process, but isn't a point "
                        "process in the NEURON library"
                    ) from None
            ma = MechAccessor(section, mod, point_process)
        else:  # Insert mechanism
            try:
                section.insert(mod_name)
            except ValueError as e:
                if str(e).find("argument not a density mechanism name") != -1:
                    raise LibraryError(f"'{mod_name}' mechanism not found") from None
            ma = MechAccessor(section, mod)
        if attributes is not None:
            ma.set(attributes)
        return ma

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

    def _load_all_libraries(self):
        if not self._loaded:
            from patch import p

            self.h = p
            self._loaded = True
            if _should_skip_load():
                return
            for path in self.get_libraries():
                dll_result = self.h.nrn_load_dll(path)
                if not dll_result:
                    raise NeuronError(
                        f"Library file could not be loaded into NEURON. Path: '{path}'"
                    )

    def get_libraries(self):
        """
        Return the locations of the library paths (dll/so) to be loaded into NEURON. Or
        perhaps for use in dark neuroscientific rituals, who knows.
        """
        if sys.platform == "win32":
            path = ["nrnmech.dll"]
        else:
            path = ["x86_64", ".libs", "libnrnmech.so"]

        return [os.path.join(folder, *path) for folder in glob(Glia.get_cache_path("*/"))]

    def is_cache_fresh(self):
        try:
            cache_data = Glia.read_cache()
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
        os.makedirs(Glia.get_data_path(), exist_ok=True)
        Glia.create_cache()
        Glia.create_preferences()
        os.makedirs(Glia.get_cache_path(), exist_ok=True)
        self._resolver = Resolver(self)
        self.compile()

    def _add_neuron_pkg(self):
        try:
            import neuron
            from neuron import h
        except ImportError:
            pass
        else:
            from patch import is_point_process, is_density_mechanism
            from .assets import Package, Mod

            nrn_pkg = Package("NEURON", neuron.__path__[0], builtin=True)
            builtin_mechs = []
            # Get all the builtin mechanisms by triggering a TypeError (NEURON 7.7 or
            # below) Or by it being a "DensityMechanism" (NEURON 7.8 or above)
            for key in dir(h):
                if is_density_mechanism(key):
                    builtin_mechs.append((key, False))
                elif is_point_process(key):
                    builtin_mechs.append((key, True))
            for mech, point_process in builtin_mechs:
                mod = Mod(nrn_pkg, mech, 0, builtin=True, is_point_process=point_process)
                nrn_pkg.mods.append(mod)
            self.packages.append(nrn_pkg)
            if self.resolver:
                self.resolver.construct_index()

    def get_mod_path(self, pkg):
        return os.path.abspath(os.path.join(pkg.path, "mod"))

    def get_neuron_mod_path(self, *paths):
        return Glia.get_cache_path(*paths)

    @staticmethod
    def _read_shared_storage(*path):
        _path = Glia.get_data_path(*path)
        try:
            with open(_path, "r") as f:
                return json.load(f)
        except IOError:
            return {}

    @staticmethod
    def _write_shared_storage(data, *path):
        _path = Glia.get_data_path(*path)
        with open(_path, "w") as f:
            f.write(json.dumps(data))

    @staticmethod
    def read_storage(*path):
        data = Glia._read_shared_storage(*path)
        glia_path = Glia.get_glia_path()
        if glia_path not in data:
            return {}
        return data[glia_path]

    @staticmethod
    def write_storage(data, *path):
        _path = Glia.get_data_path(*path)
        glia_path = Glia.get_glia_path()
        shared_data = Glia._read_shared_storage(*path)
        shared_data[glia_path] = data
        Glia._write_shared_storage(shared_data, *path)

    @staticmethod
    def read_cache():
        cache = Glia.read_storage("cache.json")
        if "mod_hashes" not in cache:
            cache["mod_hashes"] = {}
        return cache

    @staticmethod
    def write_cache(cache_data):
        Glia.write_storage(cache_data, "cache.json")

    @staticmethod
    def update_cache(cache_data):
        cache = Glia.read_cache()
        cache.update(cache_data)
        Glia.write_cache(cache)

    @staticmethod
    def create_cache():
        empty_cache = {"mod_hashes": {}, "cat_hashes": {}}
        Glia.write_cache(empty_cache)

    @staticmethod
    def read_preferences():
        return Glia.read_storage("preferences.json")

    @staticmethod
    def write_preferences(preferences):
        Glia.write_storage(preferences, "preferences.json")

    @staticmethod
    def create_preferences():
        Glia.write_storage({}, "preferences.json")

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


class MechAccessor:
    def __init__(self, section, mod, point_process=None):
        self._section_name = section.hname()
        self._section = weakref.proxy(section)
        self._mod = mod
        self._pp = point_process
        self._references = []

    def __neuron__(self):
        if self._pp is not None:
            try:
                from patch import transform

                return transform(self._pp)
            except Exception:
                pass
            return self._pp
        else:
            raise TypeError(
                "Density mechanisms can't be retrieved as a standalone Patch/NEURON "
                "entity. "
            )

    def __ref__(self, other):
        self._references.append(other)

    def __deref__(self, other):
        self._references.remove(other)

    @property
    def _connections(self):
        try:
            return self._pp._connections
        except AttributeError:
            raise TypeError("Can't connect Patch/NEURON entities to a density mechanism.")

    @_connections.setter
    def _connections(self, value):
        self._pp._connections = value

    def stimulate(self, *args, **kwargs):
        if self._pp is not None:
            return self._pp.stimulate(*args, **kwargs)
        else:
            raise TypeError("Can't stimulate a DensityMechanism.")

    def set(self, attribute_or_dict, value=None, /, x=None):
        if value is None:
            for k, v in attribute_or_dict.items():
                self.set_parameter(k, v, x)
        else:
            self.set_parameter(attribute_or_dict, value, x)

    def set_parameter(self, param, value, x=None):
        mod = self._mod.mod_name
        if self._pp is not None:
            return setattr(self._pp, param, value)
        try:
            if x is None:
                setattr(self._section.__neuron__(), f"{param}_{mod}", value)
            else:
                setattr(getattr(self._section(x), mod), value)
        except ReferenceError:
            raise ReferenceError(
                "Trying to set attribute on section"
                f" '{self._section_name}' that has since been garbage collected"
            )

    def get_parameter(self, param, x=None):
        if self._pp is not None:
            return getattr(self._pp, param)
        mod = self._mod.mod_name
        try:
            if x is None:
                return getattr(self._section.__neuron__(), f"{param}_{mod}")
            else:
                return getattr(getattr(self._section(x), mod), param)
        except ReferenceError:
            raise ReferenceError(
                "Trying to set attribute on section"
                f" '{self._section_name}' that has since been garbage collected"
            )
        except AttributeError:
            raise AttributeError(
                f"Parameter '{param}' does not exist on {self._mod.asset_name}"
            ) from None

    @property
    def parameters(self):
        raise NotImplementedError(
            "Parameter overview not implemented yet. Use `get_parameter` instead."
        )
