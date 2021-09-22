import os
from .exceptions import *
from packaging import version
from ._glia import Glia
from ._hash import get_directory_hash
import subprocess
import shutil
from tempfile import TemporaryDirectory


class Package:
    def __init__(self, name, path, builtin=False):
        self.name = name
        self.path = path
        self.mods = []
        # Exceptional flag for the NEURON builtins.
        # They need a definition to be `insert`ed,
        # but have no mod files to be compiled.
        self.builtin = builtin

    @classmethod
    def from_remote(cls, manager, advert):
        try:
            pkg = advert.package()
        except Exception as e:
            raise PackageError(
                "Could not retrieve glia package from advertised object " + str(advert)
            )
        min_astro = manager.get_minimum_astro_version()
        if not hasattr(pkg, "astro_version"):
            raise PackageVersionError(
                "Ancient Glia package '{}' too old. Minimum astro v{} required.".format(
                    pkg.name, min_astro
                )
            )
        elif version.parse(min_astro) > version.parse(pkg.astro_version):
            raise PackageVersionError(
                "Glia package too old. v{}, minimum v{} required.".format(
                    pkg.astro_version, min_astro
                )
            )
        try:
            p = cls(pkg.name, pkg.path)
            p._load_remote_mods(pkg)
        except AttributeError as e:
            raise PackageError(
                "Package '{}' is missing attributes:".format(advert.__name__)
            )
        return p

    def _load_remote_mods(self, remote_pkg):
        for mod in remote_pkg.mods:
            self.mods.append(Mod.from_remote(self, mod))

    @property
    def mod_path(self):
        return os.path.abspath(os.path.join(self.path, "mod"))


class Mod:
    def __init__(
        self,
        pkg,
        name,
        variant,
        is_point_process=False,
        is_artificial_cell=False,
        builtin=False,
    ):
        self.pkg = pkg
        self.pkg_name = pkg.name
        self.namespace = "glia__" + pkg.name
        self.asset_name = name
        self.variant = variant
        self.is_point_process = is_point_process
        self.builtin = builtin

    @classmethod
    def from_remote(cls, package, remote_object):
        excluded = ["pkg_name", "asset_name", "namespace", "pkg", "_name_statement"]
        key_map = {
            "asset_name": "name",
            "_is_point_process": "is_point_process",
            "_is_artificial_cell": "is_artificial_cell",
        }
        required = ["asset_name", "variant"]
        kwargs = {}
        # Copy over allowed
        for key, value in remote_object.__dict__.items():
            if key not in excluded:
                kwargs[key if key not in key_map else key_map[key]] = value
        for remote_attr in required:
            local_attr = (
                remote_attr if remote_attr not in key_map else key_map[remote_attr]
            )
            try:
                kwargs[local_attr] = remote_object.__dict__[remote_attr]
            except KeyError as e:
                e_str = "A mod"
                if "name" in kwargs:
                    e_str = kwargs["name"]
                raise PackageModError(
                    e_str
                    + " in {} did not specify required attribute '{}'.".format(
                        package.name, remote_attr
                    )
                )
        try:
            return cls(package, **kwargs)
        except TypeError as e:
            attr = str(e)[str(e).find("'") : -1]
            raise PackageModError(
                "Mod specified an unknown attribute {}'".format(attr)
            ) from None

    @property
    def mod_name(self):
        if self.builtin:
            return self.asset_name
        return "{}__{}__{}".format(self.namespace, self.asset_name, self.variant)

    @property
    def mod_path(self):
        return os.path.abspath(os.path.join(self.pkg.mod_path, self.mod_name + ".mod"))


class Catalogue:
    def __init__(self, name, source_file):
        self._name = name
        self._source = os.path.dirname(source_file)
        self._cache = Glia.get_cache_path(self._name, for_arbor=True)

    @property
    def name(self):
        return self._name

    @property
    def source(self):
        return self._source

    def load(self):
        import arbor

        if not self.is_fresh():
            self.build()
        return arbor.load_catalogue(self._get_library_path())

    def _get_library_path(self):
        return os.path.join(self._cache, f"{self._name}-catalogue.so")

    def is_fresh(self):
        if not os.path.exists(self._get_library_path()):
            return False
        try:
            cache_data = Glia.read_cache()
            # Backward compatibility with old installs that
            # have a JSON file without cat_hashes in it.
            cache = cache_data.get("cat_hashes", dict()).get(self._name, None)
            hash = get_directory_hash(self.get_mod_path())
            return cache == hash
        except FileNotFoundError as _:
            return False

    def get_mod_path(self):
        return os.path.abspath(os.path.join(self._source, "mod"))

    def build(self, verbose=False):
        try:
            from mpi4py.MPI import COMM_WORLD
        except:
            # No mpi4py, assume no MPI, build local on all (hopefully 1) nodes.
            self._build_local(verbose=verbose)
        else:
            # mpi4pt detected, build local on node 0. Do a collective broadcast
            # so that all processes can error out if a build error occurs on
            # node 0.
            build_err = None
            try:
                if not COMM_WORLD.Get_rank():
                    self._build_local(verbose=verbose)
            except Exception as err:
                build_err = COMM_WORLD.bcast(err, root=0)
                raise err from None
            else:
                build_err = COMM_WORLD.bcast(build_err, root=0)
                if build_err:
                    raise BuildCatalogueError(
                        "Catalogue build error, look for main node error."
                    ) from None

    def _build_local(self, verbose=False):
        mod_path = self.get_mod_path()
        with TemporaryDirectory() as tmp:
            pwd = os.getcwd()
            os.chdir(tmp)
            cmd = f"build-catalogue {self._name} {mod_path}"
            try:
                subprocess.run(
                    cmd
                    + (" --quiet" if not verbose else "")
                    + (" --verbose" if verbose else ""),
                    shell=True,
                    check=True,
                    capture_output=not verbose,
                )
            except subprocess.CalledProcessError as e:
                msg_p = (
                    f"build-catalogue errored out with exitcode {e.returncode}",
                    f"Command: {cmd}\n---- build-catalogue output ----",
                    e.stdout.decode(),
                    "---- build-catalogue error  ----",
                    e.stderr.decode(),
                )
                msg = "\n\n".join(msg_p)
                raise BuildCatalogueError(msg) from None
            os.makedirs(self._cache, exist_ok=True)
            shutil.copy2(f"{self._name}-catalogue.so", self._cache)
            os.chdir(pwd)
        # Cache directory hash of current mod files so we only rebuild on source code changes.
        cache_data = Glia.read_cache()
        cat_hashes = cache_data.setdefault("cat_hashes", dict())
        cat_hashes[self._name] = get_directory_hash(mod_path)
        Glia.update_cache(cache_data)
