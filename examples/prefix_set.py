#!/usr/bin/python3
"""Example of ``pygtrie.PrefixSet`` usage."""

__author__ = 'Michał Nazarewicz <mina86@mina86.com>'
__copyright__ = 'Copyright 2026 by Michał Nazarewicz'

# pylint: disable=missing-function-docstring

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent.parent))
import pygtrie  # pylint: disable=wrong-import-position


def main() -> None:
    print('Prefix set\n'
          '==========\n')

    ps = pygtrie.PrefixSet(factory=pygtrie.StringTrie)

    ps.add('/etc/rc.d')
    ps.add('/usr/local/share')
    ps.add('/usr/local/lib')
    ps.add('/usr')  # Will handle the above two as well
    ps.add('/usr/lib')  # Does not change anything

    print('Path prefixes:', ', '.join(iter(ps)))
    for path in ('/etc', '/etc/rc.d', '/usr', '/usr/local', '/usr/local/lib'):
        print('Is', path, 'in the set:', ('yes' if path in ps else 'no'))


if __name__ == '__main__':
    main()
