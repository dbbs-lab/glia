import setuptools, os

with open("README.md", "r") as fh:
    long_description = fh.read()

# Get the version from the glia module without importing it.
with open(os.path.join(os.path.dirname(__file__), "glia", "__init__.py"), "r") as f:
    for line in f:
        if "__version__ = " in line:
            exec(line)
            break


setuptools.setup(
    name="nrn-glia",
    version=__version__,
    author="Robin De Schepper",
    author_email="robingilbert.deschepper@unipv.it",
    description="Package manager for NEURON",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dbbs-lab/glia",
    license="GPLv3",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points={"console_scripts": ["glia = glia._cli:glia_cli"]},
    install_requires=["appdirs", "errr>=1.2.0"],
    extras_require={
        "dev": ["sphinx", "pre-commit"],
        "neuron": ["nrn-patch==4.0.0a4"],
        "arbor": ["arbor>=0.6"],
        "mpi": ["mpi4py"],
    },
)
