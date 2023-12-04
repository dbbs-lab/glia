import os
import subprocess
import sys
import warnings
import weakref
from functools import wraps
from importlib.metadata import entry_points
from shutil import copy2 as copy_file
from shutil import rmtree as rmdir

from . import _mpi
from ._fs import (
    create_cache,
    create_preferences,
    get_cache_path,
    get_data_path,
    get_mod_path,
    get_neuron_mod_path,
    read_cache,
    update_cache,
)
from ._hash import get_directory_hash
from .assets import Mod, Package
from .exceptions import (
    CatalogueError,
    CompileError,
    LibraryError,
    NeuronError,
    PackageError,
)
from .resolution import Resolver

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
        self._packages = []
        for pkg_ptr in entry_points().get("glia.package", []):
            advert = pkg_ptr.load()
            self.entry_points.append(advert)
            self._packages.append(Package.from_remote(self, advert))

    def discover_catalogues(self):
        self._catalogues = {}
        for pkg_ptr in entry_points().get("glia.catalogue", []):
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

    def start(self):
        self.compile(check_cache=True)

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
            if _mpi.main_node:
                self._compile()
            _mpi.barrier()

    @_requires_install
    def _compile(self):
        assets, mod_files, cache_data = self._collect_asset_state()
        if _should_skip_compile():
            return update_cache(cache_data)
        if len(mod_files) == 0:
            return
        neuron_mod_path = get_neuron_mod_path()
        _remove_tree(neuron_mod_path)
        # Copy over fresh mods
        for file in mod_files:
            copy_file(file, neuron_mod_path)
        # Platform specific compile
        if sys.platform == "win32":
            self._compile_nrn_windows(neuron_mod_path)
        elif sys.platform in ("linux", "darwin"):
            self._compile_nrn_linux(neuron_mod_path)
        else:
            raise NotImplementedError(
                "Only linux and win32 are supported. You are using " + sys.platform
            )
        # Update the cache with the new mod directory hashes.
        update_cache(cache_data)

    def _compile_nrn_windows(self, neuron_mod_path):
        # Compile the glia cache for Linux.
        # Runs %NEURONHOME%/nrnivmodl.bat
        from patch import p

        process = subprocess.Popen(
            [os.path.join(p.neuronhome(), "bin", "nrnivmodl.bat")],
            cwd=neuron_mod_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process.communicate(input=b"\n")
        self._compilation_failed = process.returncode != 0
        if process.returncode != 0:
            raise CompileError(stderr.decode("UTF-8"))

    def _compile_nrn_linux(self, neuron_mod_path):
        # Compile the glia cache for Linux.
        # Runs nrnivmodl.
        process = subprocess.Popen(
            ["nrnivmodl"],
            cwd=neuron_mod_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = process.communicate()
        self._compiled = process.returncode == 0
        if process.returncode != 0:
            raise CompileError(stderr.decode("UTF-8"))

    def _collect_asset_state(self):
        cache_data = read_cache()
        mod_files = []
        assets = []
        # Iterate over all discovered packages to collect the mod files.
        for pkg in self.packages:
            if pkg.builtin:
                continue
            mod_path = get_mod_path(pkg)
            for mod in pkg.mods:
                assets.append((pkg, mod))
                mod_file = mod.mod_path
                mod_files.append(mod_file)
            # Hash mod directories and their contents to update the cache data.
            cache_data["mod_hashes"][pkg.path] = get_directory_hash(mod_path)
        return assets, mod_files, cache_data

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
        if attributes is None:
            attributes = {}
        if asset.startswith("glia__"):
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
        Return the locations of the library paths (dll/so) to be loaded into NEURON.
        """
        if sys.platform == "win32":
            path = ["nrnmech.dll"]
        else:
            path = ["x86_64", ".libs", "libnrnmech.so"]

        return [get_neuron_mod_path(*path)]

    def is_cache_fresh(self):
        try:
            cache_data = read_cache()
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
        _installed = os.path.exists(get_data_path()) and os.path.exists(get_cache_path())
        return _installed

    def _install_self(self):
        os.makedirs(get_data_path(), exist_ok=True)
        create_cache()
        create_preferences()
        os.makedirs(get_cache_path(), exist_ok=True)
        self._resolver = Resolver(self)
        self.compile()

    def _add_neuron_pkg(self):
        try:
            import neuron
            from neuron import h
        except ImportError:
            pass
        else:
            import patch
            from patch import is_density_mechanism, is_point_process

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
                warnings.warn(f"Couldn't remove {file}")


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

    def record(self, param=None, x=0.5):
        from patch import p

        if param is not None and self._pp is None:
            return p.record(
                getattr(self._section(x), f"_ref_{param}_{self._mod.mod_name}")
            )
        else:
            return p.record(self)

    def __record__(self):
        if self._pp is not None:
            return self._pp.__record__()
        else:
            raise TypeError(
                "No default record for DensityMechanisms, use .record('param') instead."
            )

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
