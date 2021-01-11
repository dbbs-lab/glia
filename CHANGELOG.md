# Version 0

## 0.3.9

* Added "darwin" (Mac) compilation

## 0.3.8

* Switched to Patch 3 (beta)

## 0.3.7

* Fixed `resolve_multi` returning str

## 0.3.6

* Fixed builtin mech detection for NEURON 7.7+

## 0.3.5

* Glia now detects the builtin NEURON mechanisms.

## 0.3.4

* Finishing up resolve & wincompile issues

## 0.3.3

* `glia.resolve` added missing `self`.

## 0.3.2

* `glia.resolve` now checks installation and provides Resolver before trying to resolve.

## 0.3.1

* Fixed windows compilation process
* Context & select require install so that the resolver is guaranteed to be present.

## 0.3

* Added stable importing of the root module
* The library is only loaded once it is required, once `glia.library` is imported or once
  `glia.load_library` is called

## 0.2.0

* Added contextual preferences and general preferences.
  * Contextual preferences are nestable `with glia.context(...):` statements that keep
    a preference until the with block is exited.
  * General preferences are preferences that apply to all assets. They can currently only
    be set using contextual preferences.

## 0.1.11

* Added `packaging` to `install_requires`

## 0.1.10

* Added support for ARTIFICIAL_CELL mods.

## 0.1.9

* `glia install` installs exclusively from the GliaPI.
* Point processes are wrapped when inserted.
* Attributes can be set on mechanisms during insertion.
* The repository switched to Black formatting and has coverage and RTD documentation.

## 0.1.8

* Switched to Patch's interpreter instead of NEURON's interpreter.

## 0.1.6

* Fixed deployment issue

## 0.1.5

* Added support for point_processes. Point processes and mechanisms can be
  inserted indiscriminately with `g.insert`.
* The Mod object of a resolved mod name can be reverse looked up through the
  `Resolver.lookup` function.

## 0.1.3 & 0.1.4

Bugfixes

## 0.1.2

* Added Linux unit tests on Travis CI
* Glia checks whether packages were packaged with a recent enough Astro version.

### Bugfixes

* Glia doesn't crash anymore when trying to load preferences before being
  installed.

## 0.1.1

* Temporary release

## 0.1

* Glia can now use preferences to select a specific mod file when multiple
  packages provide the same asset, or multiple variants exist.
* Critical fix for Windows: tried to load libnrnmech.dll instead of nrnmech.dll
  and neuron.h failed silently. (Tests will be added in 0.2 to avoid this in the
  future.)
* `glia test` can now take multiple arguments for multiple tests, or no
  arguments to test all assets.
* All files will be removed from the .neuron/mod folder before compiling.

### Bugfixes

* Glia won't compile twice anymore when using `glia compile` and the cache was
  stale.

## 0.0.1

* First release of Glia
* Glia can detect glia packages and load their mod files
* Glia can compile a neuron library and load it into neuron on Linux and Windows
* Glia can resolve the simplest of selections: Give an asset name, return the first
  asset that matches. Can filter on package name and variant.
* Glia can insert those selected mechanisms into neuron sections
