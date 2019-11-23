import os, sys, argparse
glia_pkg = globals()["__package__"]
if glia_pkg is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import glia
else:
    import glia

from glia.exceptions import GliaError, ResolveError

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
    select_parser.add_argument("asset", action="store", help="The asset to set preferences for")
    select_parser.add_argument("-p","--pkg", action="store", help="Package preference for this asset")
    select_parser.add_argument("-v","--variant", action="store", help="Variant preference for this asset")
    select_parser.set_defaults(func=lambda args: select(args.asset, pkg=args.pkg, variant=args.variant, glbl=True))

    show_parser = subparsers.add_parser("show", description="Print info on an asset.")
    show_parser.add_argument("asset", action="store", help="The asset to set preferences for")
    show_parser.set_defaults(func=lambda args: _show_asset(args.asset))

    test_mech_parser = subparsers.add_parser("test", description="Test a mechanism.")
    test_mech_parser.add_argument("mechanism", action="store", help="Name of the mechanism")
    test_mech_parser.set_defaults(func=lambda args: test([args.mechanism]))

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
    glia.manager.compile()

def test(*args):
    for mechanism in args:
        glia.manager.test_mechanism(mechanism)

def list_assets(args):
    glia.manager.list_assets()

def select(asset, pkg=None, variant=None, glbl=False):
    glia.manager.select(asset, pkg=pkg, variant=variant, glbl=glbl)

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
        print("Current preferred module:", glia.manager.get_asset_full_name(pref_mod))
    print("Available modules:")
    for mod in glia.manager.resolver.index[asset]:
        print("  *", glia.manager.get_asset_full_name(mod))

if __name__ == "__main__":
    print("Careful! Executing cli.py is unsupported.")
    glia_cli()
