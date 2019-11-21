import setuptools, os

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
     name='nrn-glia',
     version='0.0.1-a5',
     author="Robin De Schepper",
     author_email="robingilbert.deschepper@unipv.it",
     description="Package manager for NEURON",
     long_description=long_description,
     long_description_content_type="text/markdown",
     url="https://github.com/dbbs-lab/glia",
     license='GPLv3',
     packages=setuptools.find_packages(),
     classifiers=[
         "Programming Language :: Python :: 3",
         "Operating System :: OS Independent",
     ],
     entry_points={
        'console_scripts': [
            'glia = glia.cli:glia_cli'
        ]
     },
 )
