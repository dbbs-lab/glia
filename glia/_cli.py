from pathlib import Path

import click

from . import _manager, _mpi
from .exceptions import *
from .packaging import PackageManager


@click.group()
def glia():
    pass


@glia.command()
def compile():
    if _mpi.main_node:
        click.echo("Glia is compiling...")
    _manager.compile()
    if _mpi.main_node:
        click.echo("Compilation complete!")
    assets, _ = _manager._precompile_cache()
    if _mpi.main_node:
        click.echo(
            "Compiled assets: "
            + ", ".join(
                set(f"{mod.pkg.name}.{mod.asset_name}({mod.variant})" for mod in assets)
            ),
        )
        click.echo("Testing assets ...")
    test(*_manager.resolver.index.keys(), standalone_mode=False)


@glia.command("list")
def list_assets():
    click.echo(
        "Assets: "
        + ", ".join(f"{e.name} ({len(e)})" for e in _manager.resolver.index.values()),
    )
    click.echo("Packages: " + ", ".join(p.name for p in _manager.packages))


@glia.command(help="Set global preferences for an asset.")
@click.argument("asset")
@click.option("-p", "--package", default=None, help="Package preference for this asset")
@click.option("-v", "--variant", default=None, help="Variant preference for this asset")
def select(asset, package, variant):
    _manager.select(asset, pkg=package, variant=variant, glbl=True)


@glia.command(help="Print info on an asset.")
@click.argument("asset")
def show(asset):
    index = _manager.resolver.index
    preferences = _manager.resolver._preferences()
    if not asset in index:
        raise click.exceptions.BadArgumentUsage(f'Unknown ASSET "{asset}"')
    if asset in preferences:
        preference = preferences[asset]
        pref_mod = None
        try:
            pref_mod = _manager.resolver.resolve_preference(asset)
        except ResolveError as e:
            click.echo("resolve error" + e)
            pass
        pref_string = ""
        if "package" in preference:
            pref_string += "pkg=" + preference["package"] + " "
        if "variant" in preference:
            pref_string += "variant=" + preference["variant"] + " "
        click.echo("Current preferences: " + pref_string)
        click.echo("Current preferred module:" + pref_mod.mod_name)
    click.echo("Available modules:")
    for mod in _manager.resolver.index[asset]:
        click.echo("  *" + mod.mod_name)


@glia.command(help="Print info on a package.")
@click.argument("package")
def show_pkg(package):
    candidates = [p for p in _manager.packages if p.name.find(package) != -1]
    if not len(candidates):
        raise click.exceptions.BadArgumentUsage(f'Unknown PACKAGE "{package}"')
    for candidate in candidates:
        click.echo("Package: " + click.style(candidate.name, fg="green"))
        click.echo("=====")
        click.echo(f"Location: {candidate.root}")
        click.echo()
        click.echo("Available modules:")
        for mod in candidate.mods:
            click.echo(f"  * {mod.mod_name} = {mod.path}")
        click.echo()


@glia.command(help="Test mechanisms")
@click.argument("mechanisms", nargs=-1)
def test(mechanisms, verbose=False):
    if len(mechanisms) == 0:
        mechanisms = _manager.resolver.index.keys()
    successes = 0
    tests = len(mechanisms)
    for mechanism in mechanisms:
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
        except AssetLookupError as e:
            mstr = "[X]"
            estr = str(e)
        if _mpi.main_node:
            click.echo(mstr, mechanism)
        if verbose and estr != "":
            if _mpi.main_node:
                click.echo("  -- " + estr)
    if _mpi.main_node:
        click.echo(f"Tests finished: {successes} out of {tests} passed")


@glia.command()
@click.argument("catalogue")
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("-d", "--debug", is_flag=True, default=False)
@click.option("--gpu/--cpu", default=False)
def build(catalogue, verbose, debug, gpu):
    _manager.build_catalogue(catalogue, verbose=verbose, debug=debug, gpu=gpu)


@glia.group(help="All commands related to packaging your NMODL files for others")
def pkg():
    pass


@pkg.command(help="Create a new Glia package.")
def new():
    from cookiecutter.main import cookiecutter

    cookiecutter(
        str((Path(__file__).parent / "packaging/cookiecutter-glia").resolve()),
    )


@pkg.command(help="Add a mod file to the current package.")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("-w", "--overwrite", is_flag=True, default=False)
@click.option("-n", "--name", prompt=True, required=True)
@click.option("-t", "--target", default=None, type=click.Path(dir_okay=False))
@click.option("-v", "--variant", default="0")
def add(source, name, variant, overwrite, target):
    source = Path(source)
    pkg = PackageManager(Path())
    mod_path = pkg.get_mod_dir(target)
    if mod_path.is_dir():
        mod_path /= f"{name}__{variant}.mod"
    if not overwrite and mod_path.exists():
        raise FileExistsError(f"Target mod file '{mod_path.resolve()}' already exists.")
    mod = pkg.get_mod_from_source(source, name=name, variant=variant)
    mod.relpath = pkg.get_rel_path(mod_path)
    pkg.add_mod_file(source, mod)


@pkg.command(help="Check for integrity problems with the package")
def check():
    pass
