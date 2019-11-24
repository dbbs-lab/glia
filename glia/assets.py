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
            raise PackageError("Could not retrieve glia package from advertised object " + str(advert))
        min_astro = manager.get_minimum_astro_version()
        if not hasattr(pkg, "astro_version"):
            raise PackageVersionError("Ancient Glia package too old. Minimum astro v{} required.".format(min_astro))
        elif version.parse(min_astro) > version.parse(pkg.astro_version):
            raise PackageVersionError("Glia package too old. v{}, minimum v{} required.".format(pkg.astro_version, min_astro))
        try:
            p = cls(pkg.name, pkg.path)
            p._load_remote_mods(pkg)
        except AttributeError as e:
            print(dir(e))
            raise PackageError("Package '{}' is missing attributes:".format(advert.name))
        return p

    def _load_remote_mods(self, remote_pkg):
        for mod in remote_pkg.mods:
            self.mods.append(Mod.from_remote(self, mod))

    @property
    def mod_path(self):
        return os.path.abspath(os.path.join(self.path, "mod"))

class Mod:
    def __init__(self, pkg, name, variant):
        self.pkg = pkg
        self.pkg_name = pkg.name
        self.namespace = "glia__" + pkg.name
        self.asset_name = name
        self.variant = variant

    @classmethod
    def from_remote(cls, package, remote_object):
        required = {'name': 'asset_name', 'variant': 'variant'}
        kwargs = {}
        for local_attr, remote_attr in required.items():
            try:
                kwargs[local_attr] = remote_object.__dict__[remote_attr]
            except KeyError as e:
                e_str = "A mod"
                if "name" in kwargs:
                    e_str = kwargs["name"]
                raise PackageModError(e_str + " in {} did not specify required attribute {}.".format(package.name, remote_attr))
        return cls(package, **kwargs)

    @property
    def mod_name(self):
        return "{}__{}__{}".format(self.namespace, self.asset_name, self.variant)

    @property
    def mod_path(self):
        return os.path.abspath(os.path.join(self.pkg.mod_path, self.mod_name + ".mod"))
