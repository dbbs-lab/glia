import click

from . import _manager, _mpi
from .exceptions import *


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
    _manager.list_assets()


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
        click.echo(f'Unknown asset "{asset}"')
        return
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
        click.echo("Package not found")
        return
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
            print(mstr, mechanism)
        if verbose and estr != "":
            if _mpi.main_node:
                print("  -- " + estr)
    if _mpi.main_node:
        click.echo(f"Tests finished: {successes} out of {tests} passed")


@glia.command()
@click.argument("catalogue")
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("-d", "--debug", is_flag=True, default=False)
@click.option("--gpu/--cpu", default=False)
def build(catalogue, verbose, debug, gpu):
    _manager.build_catalogue(catalogue, verbose=verbose, debug=debug, gpu=gpu)
