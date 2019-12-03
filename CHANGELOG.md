# Version 0

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
