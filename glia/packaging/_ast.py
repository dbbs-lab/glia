import ast
import inspect
import itertools
import typing
from copy import copy
from pathlib import Path

import black

from ..assets import Mod
from ..exceptions import PackageApiError, PackageFileError

if typing.TYPE_CHECKING:
    from nmodl import NmodlDriver


class ModuleReferences:
    def __init__(self, module: ast.Module):
        self.module_names = []
        self.pkg_names = []
        self.mod_node = None
        self.mod_names = []
        for node in module.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "glia":
                        self.module_names.append(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "glia":
                for alias in node.names:
                    if alias.name == "Mod":
                        self.mod_names.append(alias.asname or alias.name)
                    if alias.name == "Package":
                        self.pkg_names.append(alias.asname or alias.name)
                        # Store this node to insert `Mod` import if it's missing
                        self.mod_node = node

        if not (self.module_names or self.pkg_names or self.mod_names):
            raise PackageFileError("Package file is missing top-level `glia` imports.")

    def _is_call(self, node: ast.expr, attr, aliases):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in aliases:
                # Class(...)
                #   or
                # ClassAlias(...)
                return True
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == attr
                and isinstance(func.value, ast.Name)
                and func.value.id in self.module_names
            ):
                # glia.Class(...)
                #   or
                # gliaAlias.Class(...)
                return True
        return False

    def is_package_target(self, node: ast.expr):
        return self._is_call(node, "Package", self.pkg_names)

    def is_mod_target(self, node: ast.expr):
        return self._is_call(node, "Mod", self.mod_names)

    def make_mod_call_node(self):
        if self.mod_names:
            func = ast.Name(self.mod_names[0])
        else:
            if not self.module_names:
                # The package file does not contain a `Mod` import, and also no `import
                # glia` so it must contain a `from glia import Package`, so we can
                # append `, Mod`.
                self.mod_node.names.append(ast.alias("Mod"))
                self.mod_names.append("Mod")
                func = ast.Name("Mod")
            else:
                func = ast.Attribute(ast.Name(self.module_names[0]), ast.Name("Mod"))
        return ast.Call(func, [], [])

    def has_mod_ref(self):
        return self.mod_names or self.module_names


class PackageTransformer(ast.NodeTransformer):
    def __init__(self, path: Path, module: ast.Module, pkg_id: str):
        super().__init__()
        self._path = path
        self._module = module
        self._refs = ModuleReferences(self._module)
        self.pkg_node = self.get_package_declaration(pkg_id)

    @property
    def path(self):
        return self._path

    def get_package_declaration(self, pkg_id: str) -> ast.Call:
        pkg = None
        for node in self._module.body:
            if isinstance(node, ast.Assign):
                pkgs = [
                    n for n in node.targets if isinstance(n, ast.Name) and n.id == pkg_id
                ]
                if pkgs:
                    if pkg is not None:
                        raise PackageFileError(
                            f"Multiple top-level '{pkg_id}' assignments."
                        )
                    if len(node.targets) != 1:
                        raise PackageFileError(
                            "Tuple unpacking is not allowed "
                            "in package assigment statements."
                        )
                    if self._refs.is_package_target(node.value):
                        pkg = node.value
                    else:
                        raise PackageFileError(
                            f"Top-level assignment to '{pkg_id}' "
                            "is not a `glia.Package` declaration."
                        )
        if not pkg:
            raise PackageFileError(
                f"No top-level package declaration found for '{pkg_id}'"
            )
        return pkg

    def get_modlist_declaration(self) -> ast.List:
        for keyword in self.pkg_node.keywords:
            if keyword.arg == "mods":
                modlist = keyword.value
                if not isinstance(modlist, ast.List):
                    raise PackageFileError(
                        "`mods` keyword argument must be a list literal."
                    )
                for mod in modlist.elts:
                    if not self._refs.is_mod_target(mod):
                        raise PackageFileError(
                            f"'{ast.unparse(mod)}' is not a valid `glia.Mod` declaration."
                        )
                return modlist
        raise PackageFileError("Missing `mods` keyword argument for `Package` call.")

    def get_mods(self) -> list[Mod]:
        mods = []
        for mod_call in self.get_modlist_declaration().elts:
            mod_call: ast.Call
            if any(
                not isinstance(arg, ast.Constant)
                for arg in itertools.chain(
                    mod_call.args, (v.value for v in mod_call.keywords)
                )
            ):
                raise PackageFileError(
                    "Mod declarations may only use constant arguments."
                )
            mod_node = copy(mod_call)
            mod_node.func = ast.Name("Mod")
            mod_str = ast.unparse(mod_node)
            try:
                mod = eval(mod_str, {"Mod": Mod})
                mods.append(mod)
            except Exception as e:
                raise PackageFileError(
                    f"`{mod_str}` is not a valid glia.Mod declaration."
                ) from e
        return mods

    def add_mod(self, mod: Mod):
        modlist = self.get_modlist_declaration()
        modlist.elts.append(self.make_mod_node(mod))

    def make_mod_node(self, mod: Mod):
        call = self._refs.make_mod_call_node()
        for param in inspect.signature(Mod).parameters.values():
            try:
                value = getattr(mod, param.name)
            except AttributeError:
                raise PackageApiError(f"Can't read attribute `Mod.{param.name}`.")
            if value == param.default:
                continue
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                call.args.append(ast.Constant(value))
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                call.keywords.append(ast.keyword(param.name, ast.Constant(value)))
            else:
                raise PackageApiError("Couldn't process glia.Mod class arguments.")
        return call

    def write_in_place(self):
        print(
            black.format_file_contents(
                ast.unparse(self._module),
                fast=True,
                mode=black.Mode(),
            )
        )


def get_package_transformer(path: Path, pkg_id: str):
    module = ast.parse(path.read_text(), str(path))
    return PackageTransformer(path, module, pkg_id)


class NmodlWriter:
    def __init__(self, mod: Mod):
        self._mod = mod
        self._source = None
        self._driver: "NmodlDriver" = None

    @property
    def nmodl(self):
        try:
            import nmodl

            return nmodl
        except ImportError as e:
            raise RuntimeError(
                "`nmodl` package unavailable. Try to install it. If you are on Windows, "
                "please see https://github.com/BlueBrain/nmodl/issues/1112"
            ) from e

    def parse_source(self, source: Path):
        self._source = self.nmodl.NmodlDriver().parse_file(str(source.resolve()))

    def update_source_ast(self):
        if self._source is None:
            raise RuntimeError(f"No nmodl source set for {self._mod}")

    def import_source(self, source: Path, dest: Path):
        dest.mkdir(parents=True, exist_ok=True)
        mod_path = (dest / self._mod.relpath).resolve()
        self.parse_source(source)
        self.update_source_ast()
        self.write(mod_path)

    def write(self, target: Path):
        if self._source is None:
            raise RuntimeError(f"No nmodl source set for {self._mod}")
        target.write_text(self.nmodl.to_nmodl(self._source))
