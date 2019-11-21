import sys, argparse

def glia_cli():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    install_self_parser = subparsers.add_parser("install-self", description="Install the glia package manager.")
    # Install self is a dud, but it does cause this module - glia - to be
    # imported, and glia installs itself on first import.
    install_self_parser.set_defaults(func=lambda: None)

    cl_args = parser.parse_args()
    if hasattr(cl_args, 'func'):
        cl_args.func(cl_args)
