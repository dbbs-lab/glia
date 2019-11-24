import os, sys, argparse
glia_pkg = globals()["__package__"]
if glia_pkg is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import glia
else:
    import glia

from glia.exceptions import GliaError, TooManyMatchesError, UnknownAssetError, \
    LibraryError

def glia_cli():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    compile_parser = subparsers.add_parser("compile", description="Compile the NEURON mechanism library.")
    compile_parser.set_defaults(func=compile)

    # Install self is a dud, but it does cause this module - glia - to be
    # imported, and glia installs itself on first import.
    install_self_parser = subparsers.add_parser("install-self", description="Install the glia package manager.")
    install_self_parser.set_defaults(func=lambda s: None)

    install_parser = subparsers.add_parser("install", description="Install a glia package")
    install_parser.add_argument("command", action="store", help="pip install command")
    install_parser.set_defaults(func=install_package)

    install_parser = subparsers.add_parser("list", description="List all glia assets.")
    install_parser.set_defaults(func=list_assets)

    select_parser = subparsers.add_parser("select", description="Set global preferences for an asset.")
    select_parser.add_argument("asset", action="store", help="Asset name.")
    select_parser.add_argument("-p","--pkg", action="store", help="Package preference for this asset")
    select_parser.add_argument("-v","--variant", action="store", help="Variant preference for this asset")
    select_parser.set_defaults(func=lambda args: select(args.asset, pkg=args.pkg, variant=args.variant, glbl=True))

    show_parser = subparsers.add_parser("show", description="Print info on an asset.")
    show_parser.add_argument("asset", action="store", help="Asset name.")
    show_parser.set_defaults(func=lambda args: _show_asset(args.asset))

    show_pkg_parser = subparsers.add_parser("show-pkg", description="Print info on a package.")
    show_pkg_parser.add_argument("package", action="store", help="Package name")
    show_pkg_parser.set_defaults(func=lambda args: _show_pkg(args.package))

    test_mech_parser = subparsers.add_parser("test", description="Test a mechanism.")
    test_mech_parser.add_argument("mechanisms", nargs='*', action="store", help="Name of the mechanism")
    test_mech_parser.set_defaults(func=lambda args: test(*args.mechanisms))

    cl_args = parser.parse_args()
    if hasattr(cl_args, 'func'):
        try:
            cl_args.func(cl_args)
        except GliaError as e:
            print("GLIA ERROR", str(e))
            exit(1)

def install_package(args):
    glia.manager.install(args.command)
    glia.manager.start()

def compile(args):
    if not hasattr(glia.manager, "_compiled") or not glia.manager._compiled:
        glia.manager.compile()

def test(*args):
    if len(args) == 0:
        args = glia.manager.resolver.index.keys()
    successes = 0
    tests = len(args)
    for mechanism in args:
        mstr = "[OK]"
        try:
            glia.manager.test_mechanism(mechanism)
            successes += 1
        except LibraryError as _:
            mstr = "[ERROR]"
        except UnknownAssetError as _:
            mstr = "[?]"
        except TooManyMatchesError as _:
            mstr = "[MULTI]"
        print(mstr, mechanism)
    print("Tests finished:", successes, "out of", tests, "passed")

def list_assets(args):
    glia.manager.list_assets()

def select(asset, pkg=None, variant=None, glbl=False):
    glia.manager.select(asset, pkg=pkg, variant=variant, glbl=glbl)



## Prints

class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def _show_asset(asset):
    index = glia.manager.resolver.index
    preferences = glia.manager.resolver._preferences()
    if not asset in index:
        print('Unknown asset "{}"'.format(asset))
        return
    if asset in preferences:
        preference = preferences[asset]
        pref_mod = None
        try:
            pref_mod = glia.manager.resolver.resolve_preference(asset)
        except ResolveError as _:
            print("resolve error", _)
            pass
        pref_string = ""
        if "package" in preference:
            pref_string += "pkg=" + preference["package"] + " "
        if "variant" in preference:
            pref_string += "variant=" + preference["variant"] + " "
        print("Current preferences: ", pref_string)
        print("Current preferred module:", pref_mod.mod_name)
    print("Available modules:")
    for mod in glia.manager.resolver.index[asset]:
        print("  *", mod.mod_name)

def _show_pkg(pkg_name):
    candidates = list(filter(lambda p: p.name.find(pkg_name) != -1, glia.manager.packages))
    if not len(candidates):
        print("Package not found")
        return
    for candidate in candidates:
        if sys.platform == "win32":
            pstr = "Package: " + candidate.name
        else:
            pstr = "Package: " + colors.OKGREEN + candidate.name + colors.ENDC
        print(pstr)
        print("=" * len(pstr))
        print("Path: " + candidate.path)
        print("Module path: " + candidate.mod_path)
        print()
        print("Available modules:")
        for mod in candidate.mods:
            print("  *", mod.mod_name)
        print()

if __name__ == "__main__":
    print("Careful! Executing cli.py is unsupported.")
    glia_cli()
