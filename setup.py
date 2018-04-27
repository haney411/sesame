#!/usr/bin/env python3

# Copyright 2017 University of Maryland.
#
# This file is part of Sesame. It is subject to the license terms in the file
# LICENSE.rst found in the top-level directory of this distribution.
 
import sys
from setuptools import setup, Extension
from distutils.command.build_ext import build_ext
from distutils.errors import DistutilsPlatformError, DistutilsExecError, CCompilerError


CONFIG_FILE = 'setup.cfg'

ext_modules = [Extension('mumps._dmumps', sources=['mumps/_dmumps.c'])]

ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError)


class BuildFailed(Exception):
    def __init__(self):
        self.cause = sys.exc_info()[1]  # work around py 2/3 different syntax


class ve_build_ext(build_ext):
    # This class allows C extension building to fail.

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            raise BuildFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except ext_errors:
            raise BuildFailed()
        except ValueError:
            # this can happen on Windows 64 bit, see Python issue 7511
            if "'path'" in str(sys.exc_info()[1]): # works with both py 2/3
                raise BuildFailed()
            raise

cmdclass = {'build_ext': ve_build_ext}



def status_msgs(*msgs):
    print()
    for msg in msgs:
        print(msg)
    print()



def run_setup(packages, ext_modules):
    # populate the version_info dictionary with values stored in the version file
    version_info = {}
    with open('sesame/_version.py', 'r') as f:
        exec(f.read(), {}, version_info)
    
    setup(
        name = 'sesame',
        version = version_info['__version__'],
        author = 'Benoit H. Gaury',
        author_email = 'benoitgaury@gmail.com',
        packages = packages,
        cmdclass = cmdclass,
        ext_modules = ext_modules,
        classifiers = [
            'Intended Audience :: Science/Research',
            'Programming Language :: Python :: 3',
        ],
    )


packages = ['sesame']
run_setup(packages, [])
status_msgs( "Done")
