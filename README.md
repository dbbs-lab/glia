[![Build Status](https://travis-ci.org/dbbs-lab/glia.svg?branch=master)](https://travis-ci.org/dbbs-lab/glia)
[![codecov](https://codecov.io/gh/dbbs-lab/glia/branch/master/graph/badge.svg)](https://codecov.io/gh/dbbs-lab/glia)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://readthedocs.org/projects/nrn-glia/badge/?version=latest)](https://nrn-glia.readthedocs.io/en/latest/?badge=latest)

# Glia: NMODL asset manager

Glia is an NMODL asset manager for Arbor and NEURON. It collects mod files from
different pip packages and compiles them into a central library that is
automatically loaded into NEURON, or catalogues for Arbor. 
This removes the need for manual compiling and allows you
to focus on using these mechanisms across multiple models.

Changes in either the NMODL source code, or the simulator (e.g. when updating
to a new version, or rebuilding from source) result in
automatic recompilation of your mechanisms in the background.

Packaging your mod files allows you to distribute them
as dependencies of your Python models and delegates the installation,
distribution, versioning and archiving of your assets to Python's packet
manager pip.

To create Glia packages, check out the CLI tool
[Astrocyte](https://astrocyte.readthedocs.io/en/latest/). Astrocyte also
allows you to organize your personal mod collection\!

# Usage

Glia can be installed from pip:

    pip install nrn-glia

Glia will check whether packages have been added, changed or removed and
will recompile and load the library if necessary. This means that except
for importing Glia there's not much you need to do\!

``` python
from neuron import h
import glia as g

section = h.Section(name="soma")
# Load your favourite Kv1 mechanism.
g.insert(section, "Kv1")

# Note: to load the library at import time you can import glia.library instead
import glia.library
```

Glia avoids conflicts between authors and even variants of the same
mechanism and allows you to select sensible default preferences on many
levels: globally, per script, per context or per function call.

# Asset management

Glia allows for multiple assets to refer to the same mechanism by giving
them a unique name per package. The standard naming convention is as
follows:

    glia__<package-name>__<asset-name>__<variant-name>

Double underscores in packages, assets or variant names are not allowed.

This naming convention allows for multiple people to provide an
implementation of the same asset, and by using variants even one package
can provide multiple variations on the same mechanism. The default
variant is `0`

If you install multiple packages that provide the same asset, or if you
would like to specify another variant you will need to tell Glia which
one you require. You can do so by setting your asset preferences.

# Asset preferences

There are 4 different scopes for providing asset preferences:

  - **Global scope:** Selects a default mechanism asset everywhere.
  - **Script scope:** Selects a default mechanism asset for the
    remainder of the Python script.
  - **Context scope:** Select a preferred package or variant for all
    `glia.insert` calls within the context block.
  - **Single use:** Selects a mechanism asset for a single `glia.insert`
    call

## Single use

Whenever you call `glia.insert` you can append your preferences for that
insert:

``` python
g.insert('Kv1', pkg='not_my_models', variant='high_activity')
```

## Context scope

Any `glia.insert` or `glia.resolve` call within the with statement will
preferably use the given package or variant:

``` python
from patch import p
s = p.Section()
with g.context(pkg='not_my_models'):
  g.insert(s, 'Kv1')
  g.insert(s, 'Kv1', variant='high_activity')
```

You can also specify a dictionary with multiple asset-specific preferences:

``` python
from patch import p
s = p.Section()
with g.context(assets={
   'Kv1': {'package': 'not_my_models', 'variant': 'high_activity'},
   'HCN1': {'variant': 'revised'}
}):
  g.insert(s, 'Kv1')
  g.insert(s, 'HCN1')
  # Not affected by the context:
  g.insert(s, 'Kir2.3')
```

And you can even combine, preferring a certain package unless the
dictionary specifies otherwise:

``` python
from patch import p
s = p.Section()
with g.context(assets={
   'Kv1': {'package': 'not_my_models', 'variant': 'high_activity'},
   'HCN1': {'variant': 'revised'}
}, package='some_pkg_name'):
  g.insert(s, 'Kv1')
  g.insert(s, 'HCN1')
```

Finally for those of you that have really crazy preferences you can even
nest contexts, where the innermost preferences take priority.

## Script scope

Use `glia.select` to select a preferred mechanism asset, similar to the
single use syntax, for the remainder of the lifetime of the glia module:

``` python
section_global_Kv1 = h.Section()
section_local_Kv1 = h.Section()
g.insert(section_global_Kv1, 'Kv1') # Will use your global Kv1 mechanism
g.select('Kv1', pkg='not_my_models', variant='high_activity')
g.insert(section_local_Kv1, 'Kv1') # Will use the above selected Kv1 mechanism
```

## Global scope

Applying global scope uses the Glia command-line tool and will configure
glia to always select a mechanism asset as default.

Go to your favorite command-line and enter:

    glia select Kv1 --pkg=some_pkg_name --variant=non_default

This will set your preference in any script you use.
