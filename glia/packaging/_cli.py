import argparse
from pathlib import Path


def add_packaging_cli(main_parser):
    package_parser: argparse.ArgumentParser = main_parser.add_parser(
        "pkg", description="All commands related to packaging your NMODL files for others"
    )
    subparsers = package_parser.add_subparsers()
    new_parser = subparsers.add_parser("new", description="Create a new Glia package.")
    new_parser.set_defaults(func=lambda args: new_project())


def new_project():
    from cookiecutter.main import cookiecutter

    cookiecutter(str((Path(__file__).parent / "cookiecutter-glia").resolve()))
