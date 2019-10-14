# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# (C) British Crown Copyright 2017-2019 Met Office.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"init for cli and clize"

from collections import OrderedDict
from clize import parameters
from clize.help import (
    HelpForAutodetectedDocstring,
    ClizeHelp,
)
from clize.parser import value_converter
from clize.runner import Clize
from sigtools.wrappers import decorator

# selected clize imports/constants

import clize

IGNORE = clize.Parameter.IGNORE
LAST_OPTION = clize.Parameter.LAST_OPTION
REQUIRED = clize.Parameter.REQUIRED
UNDOCUMENTED = clize.Parameter.UNDOCUMENTED


# help helpers


def docutilize(obj):
    """Convert Numpy or Google style docstring into reStructuredText format.

    Args:
        obj (str or obj):
            Takes an object and changes it's docstrings to a reStructuredText
            format.
    Returns:
        (str or obj):
            A converted string or an object with replaced docstring depending
            on the type of the input.
    """
    from inspect import cleandoc
    from sphinx.ext.napoleon.docstring import GoogleDocstring, NumpyDocstring
    if isinstance(obj, str):
        doc = obj
    else:
        doc = obj.__doc__
    doc = cleandoc(doc)
    doc = str(NumpyDocstring(doc))
    doc = str(GoogleDocstring(doc))
    if isinstance(obj, str):
        return doc
    obj.__doc__ = doc
    return obj


class HelpForNapoleonDocstring(HelpForAutodetectedDocstring):
    """Help for Napolean Docstrings."""
    def add_docstring(self, docstring, *args, **kwargs):
        """Adds the updated docstring."""
        docstring = docutilize(docstring)
        super().add_docstring(docstring, *args, **kwargs)


class DocutilizeClizeHelp(ClizeHelp):
    """Subclass to build Napoleon docstring from subject."""
    def __init__(self, subject, owner,
                 builder=HelpForNapoleonDocstring.from_subject):
        super().__init__(subject, owner, builder)


# input handling


class ObjectAsStr(str):
    """Hide object under a string to pass it through Clize parser."""
    __slots__ = ('original_object',)

    def __new__(cls, obj, name=None):
        if isinstance(obj, cls):  # pass object through if already wrapped
            return obj
        if name is None:
            name = cls.object2name(obj)
        self = str.__new__(cls, name)
        self.original_object = obj
        return self

    @staticmethod
    def object2name(obj, cls=None):
        if cls is None:
            cls = type(obj)
        try:
            obj_id = hash(obj)
        except TypeError:
            obj_id = id(obj)
        return '<%s.%s@%i>' % (cls.__module__, cls.__name__, obj_id)


def maybe_coerce_with(convert, obj, **kwargs):
    """Apply converter if str, pass through otherwise."""
    obj = getattr(obj, 'original_object', obj)
    return convert(obj, **kwargs) if isinstance(obj, str) else obj


@value_converter
def inputcube(to_convert):
    """

    Args:
        to_convert (string or obj):
            calls maybe_coerce_with function with the input and load_cube.

    Returns:
        (obj):
            The result of maybe_coerce_with.

    """
    from improver.utilities.load import load_cube
    return maybe_coerce_with(load_cube, to_convert)


@value_converter
def inputjson(to_convert):
    """

    Args:
        to_convert (string or obj):
            calls maybe_coerce_with function with the input and
            load_json_or_none.

    Returns:
        (obj):
            The result of maybe_coerce_with.

    """
    from improver.utilities.cli_utilities import load_json_or_none
    return maybe_coerce_with(load_json_or_none, to_convert)


# output handling


@decorator
def with_output(wrapped, *args, output=None, **kwargs):
    """
    :param output: Output file name
    """
    from improver.utilities.save import save_netcdf
    result = wrapped(*args, **kwargs)
    if output:
        save_netcdf(result, output)
        return
    return result


@decorator
def with_intermediate_output(wrapped, *args, intermediate_output=None,
                             **kwargs):
    """
    :param intermediate_output: Output file name for intermediate result
    """

    from improver.utilities.save import save_netcdf
    result, intermediate_result = wrapped(*args, **kwargs)
    if intermediate_output:
        save_netcdf(intermediate_result, intermediate_output)
    return result


# cli object creation


def _clizefy(obj, **kwargs):
    # TODO: simplify after all CLIs are clizefied
    from ast import literal_eval
    import os
    import sys

    if hasattr(obj, 'cli'):
        return obj

    if not callable(obj):
        kwargs.pop('helper_class', None)
        return Clize.get_cli(obj, **kwargs)

    use_clize = os.environ.get('IMPROVER_USE_CLIZE')
    if use_clize:
        use_clize = literal_eval(use_clize.capitalize())

    legacy_main = getattr(sys.modules[obj.__module__], 'main', None)

    if legacy_main is None or use_clize and obj.__annotations__:
        # legacy_main is None here for any function defined in this module
        # before (and including) the main function
        return Clize.keep(obj, **kwargs)

    def _wrapper(prog: parameters.pass_name, *args):
        sys.argv[0] = prog.split()[-1]
        legacy_main(args)

    description = obj.__doc__.split('\n')[0].strip()
    _obj = Clize.as_is(_wrapper, description=description)
    obj.cli = _obj.cli

    return obj


def clizefy(func=None, helper_class=DocutilizeClizeHelp, **kwargs):
    """Decorator for creating CLI objects."""
    from functools import partial
    if func is None:
        return partial(clizefy, helper_class=helper_class, **kwargs)
    func = _clizefy(func, helper_class=helper_class, **kwargs)
    return func


# help command


@clizefy(help_names=())
def improver_help(progname: parameters.pass_name,
                  command=None, *, usage=False):
    """Show command help."""
    progname = progname.split()[0]
    args = filter(None, [command, '--help', usage and '--usage'])
    result = execute_command(SUBCOMMANDS_DISPATCHER, progname, *args)
    if not command and usage:
        result = '\n'.join(line for line in result.splitlines()
                           if not line.endswith('--help [--usage]'))
    return result


# version command


@clizefy(help_names=())
def improver_version():
    """Print version"""
    from improver import __version__
    return __version__


# mapping of command names to CLI objects


def _cli_items():
    """Dynamically discover CLIs."""
    import importlib
    import pkgutil
    from improver.cli import __path__ as improver_cli_pkg_path
    yield ('help', improver_help)
    for minfo in pkgutil.iter_modules(improver_cli_pkg_path):
        mod_name = minfo.name
        if mod_name != '__main__':
            mcli = importlib.import_module('improver.cli.' + mod_name)
            yield (mod_name, clizefy(mcli.process))


SUBCOMMANDS_TABLE = OrderedDict(sorted(_cli_items()))


# main CLI object with subcommands


SUBCOMMANDS_DISPATCHER = clizefy(
    SUBCOMMANDS_TABLE,
    description="""IMPROVER NWP post-processing toolbox""",
    footnotes="""See also improver --help for more information.""")


# IMPROVER top level main


def unbracket(args):
    """Convert input list with bracketed items into nested lists.

    >>> unbracket('foo [ bar a b ] [ baz c ] -o z'.split())
    ['foo', ['bar', 'a', 'b'], ['baz', 'c'], '-o', 'z']
    """
    outargs = []
    stack = []
    mismatch_msg = 'Mismatched bracket at position %i.'
    for i in range(0, len(args)):
        if args[i] == '[':
            stack.append(outargs)
            outargs = []
        elif args[i] == ']':
            if not stack:
                raise ValueError(mismatch_msg % i)
            stack[-1].append(outargs)
            outargs = stack.pop()
        else:
            outargs.append(args[i])
    if stack:
        raise ValueError(mismatch_msg % len(args))
    return outargs


def execute_command(dispatcher, progname, *args, verbose=False, dry_run=False):
    """Common entry point for command execution."""
    args = list(args)
    for i, arg in enumerate(args):
        if isinstance(arg, (list, tuple)):
            # process nested commands recursively
            arg = execute_command(dispatcher, progname, *arg,
                                  verbose=verbose, dry_run=dry_run)
        if not isinstance(arg, str):
            arg = ObjectAsStr(arg)
        args[i] = arg
    if dry_run:
        result = args  # poor man's dry run!
    else:
        result = dispatcher(progname, *args)
    if verbose or dry_run:
        print(progname, *args, ' -> ', ObjectAsStr.object2name(result))
    return result


@clizefy(alt={'version': improver_version})
def main(progname: parameters.pass_name,
         command: LAST_OPTION,
         *args,
         verbose=False,
         dry_run=False):
    """IMPROVER NWP post-processing toolbox

    Results from commands can be passed into file-like arguments
    of other commands by surrounding them by square brackets::

        improver command [ command ... ] ...

    Spaces around brackets are mandatory.

    Args:
        command (str):
            Command to execute
        args (tuple):
            Command arguments
        verbose (bool):
            Print executed commands
        dry_run (bool):
            Print commands to be executed

    See improver help [--usage] [command] for more information
    on available command(s).
    """
    args = unbracket(args)
    result = execute_command(SUBCOMMANDS_DISPATCHER,
                             progname, command, *args,
                             verbose=verbose, dry_run=dry_run)
    return result


def run_main(argv=None):
    from clize import run
    import sys
    # clize shows module execution as`python -m improver.cli`
    # override argv[0] and pass it explicitly in order to avoid this
    if argv is None:
        argv = sys.argv[:]
        argv[0] = 'improver'
    run(main, args=argv)
