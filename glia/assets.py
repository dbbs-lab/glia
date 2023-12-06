import os
import shutil
import subprocess
import typing
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from . import _mpi
from ._fs import get_cache_path, read_cache, update_cache
from ._hash import get_directory_hash, get_package_hash, get_package_mods_hash
from .exceptions import *

if typing.TYPE_CHECKING:
    import arbor


class Package:
    def __init__(self, name: str, root: Path, *, mods: list["Mod"] = None, builtin=False):
        self._name = name
        self._root = Path(root)
        self.path = None
        self.mods: list["Mod"] = [] if mods is None else mods
        # Exceptional flag for the NEURON builtins.
        # They need a definition to be `insert`ed,
        # but have no mod files to be compiled.
        self.builtin = builtin

    def __hash__(self):
        return get_package_hash(self)

    @property
    def name(self):
        return self._name

    @property
    def hash(self):
        return get_package_mods_hash(self)

    @property
    def root(self):
        return self._root


class Mod:
    def __init__(
        self,
        relpath: str,
        name,
        variant,
        is_point_process=False,
        is_artificial_cell=False,
        dialect: typing.Union[typing.Literal["arbor"], typing.Literal["neuron"]] = None,
        builtin=False,
    ):
        self._pkg: typing.Optional[Package] = None
        self._relpath = relpath
        self.asset_name = name
        self.variant = variant
        self.is_point_process = is_point_process
        self.is_artificial_cell = is_artificial_cell
        self.dialect = dialect
        self.builtin = builtin

    def set_package(self, package: Package):
        self._pkg = package

    @property
    def pkg(self):
        return self._pkg

    @property
    def pkg_name(self):
        return self._pkg.name

    @property
    def mech_id(self):
        return (self.asset_name, self.variant, self.pkg_name)

    @property
    def mod_name(self):
        if self.builtin:
            return self.asset_name
        return f"glia__{self.asset_name}__{self.variant}"

    @property
    def mod_path(self):
        return self.pkg.root / self._relpath


class Catalogue:
    def __init__(self, name, source_file):
        self._name = name
        self._source = os.path.dirname(source_file)
        self._cache = get_cache_path(self._name, prefix="_arb")

    @property
    def name(self):
        return self._name

    @property
    def source(self):
        return self._source

    def load(self) -> "arbor.catalogue":
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
            cache_data = read_cache()
            # Backward compatibility with old installs that
            # have a JSON file without cat_hashes in it.
            cached = cache_data.get("cat_hashes", dict()).get(self._name, None)
            return cached == self._hash()
        except FileNotFoundError as _:
            return False

    def _hash(self):
        import arbor

        source_hash = get_directory_hash(self.get_mod_path())
        arbor_hash = str(arbor.config())
        return source_hash + arbor_hash

    def get_mod_path(self):
        return os.path.abspath(os.path.join(self._source, "mod"))

    def build(self, verbose=None, debug=False, gpu=None):
        # Turn verbosity on if debug is on, unless it's explicitly toggled off.
        verbose = False if verbose is False else verbose or debug

        def run_build():
            self._build_local(verbose, debug, gpu)

        build_err = None
        try:
            if _mpi.main_node:
                run_build()
        except Exception as err:
            _mpi.bcast(err)
            raise err from None
        else:
            build_err = _mpi.bcast(build_err)
            if build_err:
                raise BuildCatalogueError(
                    "Catalogue build error, look for main node error."
                ) from None

    def _build_local(self, verbose, debug, gpu):
        tmp_dir = TemporaryDirectory
        if debug:
            # Temp dir context manager that doesn't clean up the build folder so that
            # the generated cpp code can be debugged
            class TmpDir:
                def __enter__(*args, **kwargs):
                    return mkdtemp()

                def __exit__(*args, **kwargs):
                    pass

            tmp_dir = TmpDir

        mod_path = self.get_mod_path()
        with tmp_dir() as tmp:
            pwd = os.getcwd()
            os.chdir(tmp)
            cmd = f"arbor-build-catalogue {self._name} {mod_path}"
            try:
                subprocess.run(
                    cmd
                    + (" --quiet" if not verbose else "")
                    + (" --verbose" if verbose else "")
                    + (" --debug" if debug else "")
                    + (f" --gpu={gpu}" if gpu else ""),
                    shell=True,
                    check=True,
                    capture_output=not verbose,
                )
            except subprocess.CalledProcessError as e:
                msg_p = [f"ABC errored out with exitcode {e.returncode}"]
                if verbose:
                    msg_p += ["Check log above for error."]
                else:
                    msg_p += [
                        f"Command: {cmd}\n---- ABC output ----",
                        e.stdout.decode(),
                        "---- ABC error  ----",
                        e.stderr.decode(),
                    ]
                msg = "\n\n".join(msg_p)
                raise BuildCatalogueError(msg) from None
            os.makedirs(self._cache, exist_ok=True)
            shutil.copy2(f"{self._name}-catalogue.so", self._cache)
            os.chdir(pwd)
            if debug:
                print(f"Debug copy of catalogue in '{tmp}'")
        # Cache directory hash of current mod files so we only rebuild on source code
        # changes.
        cache_data = read_cache()
        cat_hashes = cache_data.setdefault("cat_hashes", dict())
        cat_hashes[self._name] = self._hash()
        update_cache(cache_data)
