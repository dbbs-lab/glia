import ast
import itertools
import typing
import warnings
from copy import copy
from pathlib import Path

from ..assets import Mod
from ..exceptions import PackageFileError, PackageWarning


class ModuleReferences:
    def __init__(self, module: ast.Module):
        self.module_names = []
        self.pkg_names = []
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
                        warnings.warn(
                            f"Multiple top-level '{pkg_id} =' statements.", PackageWarning
                        )
                    if len(node.targets) != 1:
                        raise PackageFileError(
                            "Tuple unpacking is not allowed in package assigment statements."
                        )
                    if self._refs.is_package_target(node.value):
                        pkg = node.value
        if not pkg:
            raise PackageFileError(
                f"No top-level package declaration found for '{pkg_id}'"
            )
        return pkg

    def get_mod_declarations(self) -> typing.List[ast.Call]:
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
                return modlist.elts
        raise PackageFileError("Missing `mods` keyword argument for `Package` call.")

    def get_mods(self):
        mods = []
        for mod_call in self.get_mod_declarations():
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
                mods.append(eval(mod_str, {"Mod": Mod}))
            except Exception as e:
                raise PackageFileError(
                    f"`{mod_str}` is not a valid glia.Mod declaration."
                ) from e
        return mods


def get_package_transformer(path: Path, pkg_id: str):
    module = ast.parse(path.read_text(), str(path))
    return PackageTransformer(path, module, pkg_id)
