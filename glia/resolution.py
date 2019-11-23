from .exceptions import ResolveError, TooManyMatchesError, NoMatchesError

class IndexEntry:
    def __init__(self, name):
        self.name = name
        self.items = []

    def __call__(self):
        return self.items

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def append(self, asset):
        self.items.append(asset)

class Resolver:

    def __init__(self, manager):
        self.manager = manager
        self.global_preferences = self.manager.read_preferences()
        self.local_preferences = {}
        # self.index = self.manager.read_index()
        self.construct_index()

    def construct_index(self):
        packages = self.manager.packages
        self.index = {}
        for pkg in packages:
            for mod in pkg.mods:
                name = mod.asset_name
                if not name in self.index:
                    self.index[name] = IndexEntry(name)
                self.index[name].append(mod)

    def resolve(self, asset_name, pkg=None, variant=None):
        if not asset_name in self.index:
            raise ResolveError("Selection could not be resolved: Asset '{}' not found.".format(asset_name))

        # Try resolving with preference
        if self.has_preference(asset_name):
            resolve_name = self.resolve_preference(asset_name, pkg=pkg, variant=variant)
            if not resolve_name is None:
                return resolve_name

        # If there was no preference, or if the preference couldn't provide the
        # selection criteria, try resolving without preference.

        mods = iter(self.index[asset_name])
        if pkg:
            mods = filter(lambda m: m.pkg_name == pkg, mods)
        if variant:
            mods = filter(lambda m: m.variant == variant, mods)
        resolved = list(mods)
        if len(resolved) == 0:
            raise NoMatchesError("Selection could not be resolved.")
        resolve_name = self.manager.get_asset_full_name(resolved[0])
        if len(resolved) > 1:
            # If all candidates are from the same package, and 1 is the default variant
            # then return that default variant
            if all(map(lambda m: m.pkg_name == resolved[0].pkg_name, resolved)) \
              and any(map(lambda m: m.variant == "0", resolve)):
                return list(filter(lambda m: m.variant == "0", resolve))[0]
            criterium = asset_name
            if pkg:
                criterium = pkg + "." + asset_name
            if variant:
                criterium += " ({})".format(variant)
            raise TooManyMatchesError(
                "Selection could not be resolved, too many matches for '{}':\n  * ".format(criterium) +
                "\n  * ".join(list(map(lambda r: self.manager.get_asset_full_name(r), resolved))) +
                '\n Try specifying a package or variant'
            )
        return resolve_name

    def has_preference(self, asset_name):
        return asset_name in self._preferences()

    def resolve_preference(self, asset_name, pkg=None, variant=None):
        raise NotImplementedError()

    def _preferences(self):
        pref = self.global_preferences.copy()
        pref.update(self.local_preferences)
        return pref
