class GliaError(Exception):
    pass

class CompileError(GliaError):
    pass

class LibraryError(GliaError):
    pass
