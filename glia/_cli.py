import os, sys, argparse
from . import _manager
from .exceptions import *

try:
    from patch import p

    p.nrnmpi_init()
    import mpi4py.MPI

    main_node = not mpi4py.MPI.COMM_WORLD.Get_rank()
except ImportError:
    main_node = True


def glia_cli():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    compile_parser = subparsers.add_parser(
        "compile", description="Compile the NEURON mechanism library."
    )
    compile_parser.set_defaults(func=compile)

    list_parser = subparsers.add_parser("list", description="List all glia assets.")
    list_parser.set_defaults(func=list_assets)

    select_parser = subparsers.add_parser(
        "select", description="Set global preferences for an asset."
    )
    select_parser.add_argument("asset", action="store", help="Asset name.")
    select_parser.add_argument(
        "-p", "--pkg", action="store", help="Package preference for this asset"
    )
    select_parser.add_argument(
        "-v", "--variant", action="store", help="Variant preference for this asset"
    )
    select_parser.set_defaults(
        func=lambda args: select(
            args.asset, pkg=args.pkg, variant=args.variant, glbl=True
        )
    )

    show_parser = subparsers.add_parser("show", description="Print info on an asset.")
    show_parser.add_argument("asset", action="store", help="Asset name.")
    show_parser.set_defaults(func=lambda args: _show_asset(args.asset))

    show_pkg_parser = subparsers.add_parser(
        "show-pkg", description="Print info on a package."
    )
    show_pkg_parser.add_argument("package", action="store", help="Package name")
    show_pkg_parser.set_defaults(func=lambda args: _show_pkg(args.package))

    test_mech_parser = subparsers.add_parser("test", description="Test a mechanism.")
    test_mech_parser.add_argument(
        "mechanisms", nargs="*", action="store", help="Name of the mechanism"
    )
    test_mech_parser.add_argument(
        "--verbose", action="store_true", help="Show error messages"
    )
    test_mech_parser.set_defaults(
        func=lambda args: test(*args.mechanisms, verbose=args.verbose)
    )

    build_parser = subparsers.add_parser("build", description="Build a catalogue.")
    build_parser.add_argument("cat_name", action="store", help="Catalogue name")
    build_parser.add_argument("--verbose", action="store_true", help="Verbose mode")
    build_parser.add_argument("--debug", action="store_true", help="Debug mode")
    build_parser.add_argument("--gpu", action="store", help="Build with GPU support")
    build_parser.set_defaults(func=lambda args: _build_cat(args))

    cl_args = parser.parse_args()
    if hasattr(cl_args, "func"):
        try:
            cl_args.func(cl_args)
        except GliaError as e:  # pragma: no cover
            print("GLIA ERROR", str(e))
            sys.exit(1)


def compile(args):
    if main_node:
        print("Glia is compiling...")
    _manager._compile()
    if main_node:
        print("Compilation complete!")
    assets, _, _ = _manager._collect_asset_state()
    if main_node:
        print(
            "Compiled assets:",
            ", ".join(
                list(
                    set(
                        map(
                            lambda a: a[0].name
                            + "."
                            + a[1].asset_name
                            + "({})".format(a[1].variant),
                            assets,
                        )
                    )
                )
            ),
        )
        print("Testing assets ...")
    test(*_manager.resolver.index.keys())


def test(*args, verbose=False):
    if len(args) == 0:
        args = _manager.resolver.index.keys()
    successes = 0
    tests = len(args)
    for mechanism in args:
        mstr = "[OK]"
        estr = ""
        try:
            _manager.test_mechanism(mechanism)
            successes += 1
        except LibraryError as e:
            mstr = "[ERROR]"
            estr = str(e)
        except UnknownAssetError as _:
            mstr = "[?]"
        except TooManyMatchesError as e:
            mstr = "[MULTI]"
            estr = str(e)
        except LookupError as e:
            mstr = "[X]"
            estr = str(e)
        if main_node:
            print(mstr, mechanism)
        if verbose and estr != "":
            if main_node:
                print("  -- " + estr)
    if main_node:
        print("Tests finished:", successes, "out of", tests, "passed")


def list_assets(args):
    _manager.list_assets()


def select(asset, pkg=None, variant=None, glbl=False):
    _manager.select(asset, pkg=pkg, variant=variant, glbl=glbl)


## Prints


class _colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def _show_asset(asset):
    index = _manager.resolver.index
    preferences = _manager.resolver._preferences()
    if not asset in index:
        print('Unknown asset "{}"'.format(asset))
        return
    if asset in preferences:
        preference = preferences[asset]
        pref_mod = None
        try:
            pref_mod = _manager.resolver.resolve_preference(asset)
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
    for mod in _manager.resolver.index[asset]:
        print("  *", mod.mod_name)


def _show_pkg(pkg_name):
    candidates = list(filter(lambda p: p.name.find(pkg_name) != -1, _manager.packages))
    if not len(candidates):
        print("Package not found")
        return
    for candidate in candidates:
        if sys.platform == "win32":
            pstr = "Package: " + candidate.name
        else:
            pstr = "Package: " + _colors.OKGREEN + candidate.name + _colors.ENDC
        print(pstr)
        print("=" * len(pstr))
        print("Path: " + candidate.path)
        print("Module path: " + candidate.mod_path)
        print()
        print("Available modules:")
        for mod in candidate.mods:
            print("  *", mod.mod_name)
        print()


def _build_cat(args):
    return _manager.build_catalogue(
        args.cat_name, verbose=args.verbose, debug=args.debug, gpu=args.gpu
    )
