import os, sys, argparse
glia_pkg = globals()["__package__"]
if glia_pkg is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import glia
else:
    import glia

from glia.exceptions import GliaError

def glia_cli():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    install_self_parser = subparsers.add_parser("install-self", description="Install the glia package manager.")
    # Install self is a dud, but it does cause this module - glia - to be
    # imported, and glia installs itself on first import.
    install_self_parser.set_defaults(func=lambda: None)

    install_parser = subparsers.add_parser("install", description="Install a glia package")
    install_parser.add_argument("command", action="store", help="pip install command")
    install_parser.set_defaults(func=install_package)

    install_parser = subparsers.add_parser("compile", description="Compile the NEURON mechanism library.")
    install_parser.set_defaults(func=compile)

    test_mech_parser = subparsers.add_parser("test", description="Test a mechanism.")
    test_mech_parser.add_argument("mechanism", action="store", help="Name of the mechanism")
    test_mech_parser.set_defaults(func=test_mech)

    cl_args = parser.parse_args()
    if hasattr(cl_args, 'func'):
        try:
            cl_args.func(cl_args)
        except GliaError as e:
            print("GLIA ERROR", str(e))
            exit(1)


def install_package(args):
    glia.manager.install(args.command)

def compile(args):
    glia.manager.compile()

def test_mech(args):
    glia.manager.test_mechanism(args.mechanism)

if __name__ == "__main__":
    print("Running glia-cli script.")
    glia_cli()
