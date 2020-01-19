Usage
=====

Glia can be installed from pip::

   pip install nrn-glia

When Glia is imported it will check for glia packages and compile them into
a library for NEURON, afterwards immediatly loading it into NEURON aswell:

.. code-block:: python

   from neuron import h
   import glia as g

Only assets following the Glia naming convention will be included in the library
and are available either directly using their namespaced name, or using
``glia.insert``:

.. code-block:: python

   section = h.Section(name="soma")
   # Add the default Kv1 mechanism provided in the `example` package.
   section.insert("glia__example__Kv1__0")
   # Preferably use glia's mechanism resolver to load your favourite Kv1 mechanism.
   g.insert(section, "Kv1")

Asset management
================

Glia allows for multiple assets to refer to the same mechanism by giving them
a unique name per package. The standard naming convention is as follows::

   glia__<package-name>__<asset-name>__<variant-name>

Double underscores in packages, assets or variant names are not allowed.

This naming convention allows for multiple people to provide an implementation
of the same asset, and by using variants even one package can provide multiple
variations on the same mechanism. The default variant is ``0``

If you install multiple packages that provide the same asset, or if you would like to
specify another variant you will need to tell Glia which one you require. You can do so by
setting your asset preferences.

Asset preferences
=================

There are 3 different scopes for providing asset preferences:

* **Global scope:** Selects a default mechanism asset everywhere.
* **Script scope:** Selects a default mechanism asset for the remainder of the Python script.
* **Single use:** Selects a mechanism asset for a single ``glia.insert`` call

Single use
~~~~~~~~~~

Whenever you call ``glia.insert`` you can append your preferences for that insert:

.. code-block:: python

   g.insert('Kv1', pkg='not_my_models', variant='high_activity')


Script scope
~~~~~~~~~~~~

Use ``glia.select`` to select a preferred mechanism asset, similar to the single
use syntax:

.. code-block:: python

   section_global_Kv1 = h.Section()
   section_local_Kv1 = h.Section()
   g.insert(section_global_Kv1, 'Kv1') # Will use your global Kv1 mechanism
   g.select('Kv1', pkg='not_my_models', variant='high_activity')
   g.insert(section_local_Kv1, 'Kv1') # Will use the above selected Kv1 mechanism


Global scope
~~~~~~~~~~~~

Applying global scope uses the Glia command-line tool and will configure glia
to always select a mechanism asset as default.

Go to your favorite command-line tool and execute:

.. code-block::

   glia select Kv1 --pkg=some_pkg_name --variant=non_default

This will set your preference in any script you use, provided they load glia from the
same path (e.g. not the case in different virtual environments).
