class GliaError(Exception):
    pass

class CompileError(GliaError):
    pass

class LibraryError(GliaError):
    pass

class NeuronError(GliaError):
    pass

class ResolveError(GliaError):
    pass

class TooManyMatchesError(ResolveError):
    pass

class NoMatchesError(ResolveError):
    pass

class UnknownAssetError(ResolveError):
    pass

class PackageError(GliaError):
    pass

class PackageModError(PackageError):
    pass

class PackageVersionError(PackageError):
    pass
