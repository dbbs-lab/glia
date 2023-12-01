from typing import Type

from errr.tree import exception as _e
from errr.tree import make_tree as _make_tree

_make_tree(
    globals(),
    GliaError=_e(
        CompileError=_e(),
        LibraryError=_e(),
        NeuronError=_e(),
        LookupError=_e(),
        ResolveError=_e(
            TooManyMatchesError=_e("matches", "asset", "pkg", "variant"),
            NoMatchesError=_e("pkg", "variant"),
            UnknownAssetError=_e(),
        ),
        PackageError=_e(
            PackageModError=_e(),
            PackageVersionError=_e(),
        ),
        CatalogueError=_e(BuildCatalogueError=_e()),
    ),
)

GliaError: Type[Exception]
CompileError: Type[GliaError]
LibraryError: Type[GliaError]
NeuronError: Type[GliaError]
LookupError: Type[GliaError]
ResolveError: Type[GliaError]
TooManyMatchesError: Type[ResolveError]
NoMatchesError: Type[ResolveError]
UnknownAssetError: Type[ResolveError]
PackageError: Type[GliaError]
PackageModError: Type[PackageError]
PackageVersionError: Type[PackageError]
CatalogueError: Type[GliaError]
BuildCatalogueError: Type[CatalogueError]
