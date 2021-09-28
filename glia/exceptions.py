from errr.tree import make_tree as _make_tree, exception as _e

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
