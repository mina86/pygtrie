#!/usr/bin/python3
"""Example of ``pygtrie.StringTrie`` usage."""

__author__ = 'Michał Nazarewicz <mina86@mina86.com>'
__copyright__ = 'Copyright 2026 by Michał Nazarewicz'

# pylint: disable=missing-function-docstring

import pathlib
import sys
import typing

sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent.parent))
import pygtrie  # pylint: disable=wrong-import-position


Handler = typing.Callable[[str], None]

def define_routes() -> pygtrie.StringTrie[Handler]:
    routes: pygtrie.StringTrie[Handler] = pygtrie.StringTrie(separator='/')
    routes[''] =         lambda path: print(f'Root handler: {path}')
    routes['/foo'] =     lambda path: print(f'Foo handler: {path}')
    routes['/foo/bar'] = lambda path: print(f'FooBar handler: {path}')
    routes['/baz'] =     lambda path: print(f'Baz handler: {path}')
    return routes


PATHS = ('/', '/foo', '/foo/bar', '/foo/bar/baz', '/qux', 'invalid')


def no_handler(path: str) -> None:
    print(f'Handle not found for ‘{path}’')


def main() -> None:
    print('Simulating URL routing\n'
          '======================\n')

    routes = define_routes()

    print('* Using prefix.value:')
    for path in PATHS:
        # `prefix` make by a real prefix or a ‘none step’ if no prefix is found.
        # The object implements truth value testing which can be used to
        # determine whether a valid prefix was found.
        prefix = routes.longest_prefix(path)
        if prefix:
            prefix.value(path)
        else:
            no_handler(path)

    print()
    print('* Using prefix.get:')
    for path in PATHS:
        # This does the same as above, but is more concise.
        handler = routes.longest_prefix(path).get(no_handler)
        handler(path)


if __name__ == '__main__':
    main()
