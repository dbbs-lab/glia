class IndexEntry:
    def __init__(self, name):
        self.name = name
        self.items = []

    def __call__(self):
        return self.items

    def append(self, asset):
        self.items.append(asset)

class Resolver:

    def __init__(self, manager):
        self.manager = manager
        # self.preferences = self.manager.read_preferences()
        # self.index = self.manager.read_index()
        self.index = {}
        self.construct_index()

    def construct_index(self):
        packages = self.manager.packages
        for pkg in packages:
            for mod in pkg.mods:
                name = mod.asset_name
                if not name in self.index:
                    self.index[name] = IndexEntry(name)
                self.index[name].append(mod)

    def resolve(self, asset_name, pkg=None, variant=None):
        if not asset_name in self.index:
            raise ResolveError("Selection could not be resolved: Asset '{}' not found.".format(asset_name))
        mods = self.index[asset_name]()
        if pkg:
            mods = filter(lambda m: m.pkg_name == pkg, mods)
        if variant:
            mods = filter(lambda m: m.variant == variant, mods)
        resolved = list(mods)
        if len(resolved) == 0:
            raise ResolveError("Selection could not be resolved.")
        else:
            return self.manager.get_asset_full_name(resolved[0])
