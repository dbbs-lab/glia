import ast
from ast import NodeTransformer, NodeVisitor

from ..exceptions import PackageFileError


class FindImportVisitor(NodeVisitor):
    def __init__(self):
        self.module_names = []
        self.mod_names = []
        self.pkg_names = []
        self.depth = -1

    def visit(self, node):
        self.depth += 1
        super().visit(node)
        self.depth -= 1
        if self.depth < 0:
            if not (self.module_names or (self.pkg_names and self.mod_names)):
                raise PackageFileError(
                    "Package file does not appear to contain top-level `glia` imports."
                )

    def visit_Import(self, node):
        if self.depth == 1:
            for alias in node.names:
                if alias.name == "glia":
                    self.module_names.append(alias.asname or alias.name)

    def visit_ImportFrom(self, node):
        if self.depth == 1 and node.module == "glia":
            for alias in node.names:
                if alias.name == "Mod":
                    self.mod_names.append(alias.asname or alias.name)
                if alias.name == "Package":
                    self.pkg_names.append(alias.asname or alias.name)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in self.pkg_names:
                print("PKG CALL")
            elif node.func.id == "Mod":
                print("MOD CALL")


class FindPackageVisitor(FindImportVisitor):
    def __init__(self, pkg_id):
        super().__init__()
        self.pkg_id = pkg_id
        self.pkg_node = None

    def visit_Assign(self, node):
        # package = ...
        pkg = [n for n in node.targets if isinstance(n, ast.Name) and n.id == self.pkg_id]
        if pkg:
            if self.pkg_node is not None:
                raise PackageFileError("Duplicate `package` statements.")
            if len(node.targets) != 1:
                raise PackageFileError("`package` statement must be simple assignment.")
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name) and func.id in self.pkg_names:
                    # package = Package(...)
                    # package = PkgAlias(...)
                    self.pkg_node = node.value
                elif (
                    isinstance(func, ast.Attribute)
                    and func.attr == "Package"
                    and isinstance(func.value, ast.Name)
                    and func.value.id in self.module_names
                ):
                    # package = glia.Package(...)
                    # package = gliaAlias.Package(...)
                    self.pkg_node = node.value


def find_package(pkg_id, body):
    visitor = FindPackageVisitor(pkg_id)
    visitor.visit(body)
    if visitor.pkg_node is None:
        raise PackageFileError(f"Package `{pkg_id}` not found.")
    else:
        return visitor.pkg_node
