class GliaError(Exception):
    pass

class CompileError(GliaError):
    pass

class LibraryError(GliaError):
    pass

class ResolveError(GliaError):
    pass

class TooManyMatchesError(ResolveError):
    pass

class NoMatchesError(ResolveError):
    pass

class PackageError(GliaError):
    pass

class PackageModError(GliaError):
    pass
