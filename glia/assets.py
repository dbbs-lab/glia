import os
from .exceptions import PackageError, PackageModError, PackageVersionError
from packaging import version


class Package:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.mods = []

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
