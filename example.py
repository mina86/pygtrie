#!/usr/bin/python

"""trie module example code."""

from __future__ import absolute_import, division, print_function

__author__ = 'Michał Nazarewicz <mina86@mina86.com>'
__copyright__ = 'Copyright 2014 Google LLC'

import os
import stat
import sys
import typing

import pygtrie

# pylint: disable=invalid-name,redefined-outer-name

print('Storing file information in the trie')
print('====================================\n')

ROOT_DIR = '/usr/local'
SUB_DIR = os.path.join(ROOT_DIR, 'lib')
SUB_DIRS = tuple(os.path.join(ROOT_DIR, d)
                 for d in ('lib', 'lib32', 'lib64', 'share'))

paths = pygtrie.StringTrie(separator=os.path.sep)

# Read sizes regular files into a Trie
for dirpath, unused_dirnames, filenames in os.walk(ROOT_DIR):
    for filename in filenames:
        filename = os.path.join(dirpath, filename)
        try:
            filestat = os.stat(filename)
        except OSError:
            continue
        if stat.S_IFMT(filestat.st_mode) == stat.S_IFREG:
            paths[filename] = filestat.st_size

# Size of all files we've scanned
print('Size of %s: %d' % (ROOT_DIR, sum(paths.itervalues())))

# Size of all files of a sub-directory
print('Size of %s: %d' % (SUB_DIR, sum(paths.itervalues(prefix=SUB_DIR))))

# Check existence of some directories
for directory in SUB_DIRS:
    if paths.has_subtrie(directory):
        print(directory, 'exists')
    else:
        print(directory, 'does not exist')

# Drop a subtrie
print('Dropping', SUB_DIR)
del paths[SUB_DIR:]
print('Size of %s: %d' % (ROOT_DIR, sum(paths.itervalues())))
for directory in SUB_DIRS:
    if paths.has_subtrie(directory):
        print(directory, 'exists')
    else:
        print(directory, 'does not exist')


print('\nStoring URL handlers map')
print('========================\n')

prefixes = pygtrie.CharTrie()
prefixes['/'] =       lambda url: print(f'Root handler: {url}')
prefixes['/foo'] =    lambda url: print(f'Foo handler: {url}')
prefixes['/foobar'] = lambda url: print(f'FooBar handler: {url}')
prefixes['/baz'] =    lambda url: print(f'Baz handler: {url}')

for url in ('/', '/foo', '/foot', '/foobar', 'invalid', '/foobarbaz', '/ba'):
    handler = prefixes.longest_prefix(url).get()
    if handler:
        handler(url)
    else:
        print('Unable to handle', repr(url))


print('\nCustom key-path conversion')
print('==========\n')

class PostalTrie(pygtrie.Trie):
    """An example Trie which uses ‘xx-yyy’ postal codes as keys.

    The ‘xx-yyy’ key is split into integers: ``(xx, y, y, y)``.  The class
    demonstrates usage of ``_path_from_key`` and ``_key_from_path`` methods.
    """

    def _path_from_key(self, key: str) -> typing.Sequence[int]:
        if '-' not in key:
            return [int(key)] if key else ()
        head, tail = key.split('-')
        return [int(head)] + [int(digit) for digit in tail]

    def _key_from_path(self, path: typing.Iterable[int]) -> str:
        path = iter(path)
        try:
            head = next(path)
        except StopIteration:
            return ''  # empty path
        tail = ''.join(str(digit) for digit in path)
        if tail:
            return f'{head:02}-{tail}'
        else:
            return f'{head:02}'

trie = PostalTrie()
trie['00-325'] = True
trie['28-133'] = True
trie['30-001'] = True

for code in trie.keys():
    print(code)


try:
    import termios
    import tty

    def getch():
        """Reads single character from standard input."""
        attr = termios.tcgetattr(0)
        try:
            tty.setraw(0)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(0, termios.TCSADRAIN, attr)

except ImportError:
    try:
        from msvcrt import getch  # pylint: disable=import-error
    except ImportError:
        sys.exit(0)


print('\nPrefix set')
print('==========\n')

ps = pygtrie.PrefixSet(factory=pygtrie.StringTrie)

ps.add('/etc/rc.d')
ps.add('/usr/local/share')
ps.add('/usr/local/lib')
ps.add('/usr')  # Will handle the above two as well
ps.add('/usr/lib')  # Does not change anything

print('Path prefixes:', ', '.join(iter(ps)))
for path in ('/etc', '/etc/rc.d', '/usr', '/usr/local', '/usr/local/lib'):
    print('Is', path, 'in the set:', ('yes' if path in ps else 'no'))


if not os.isatty(0):
    sys.exit(0)


print('\nDictionary test')
print('===============\n')

words = pygtrie.CharTrie()
words['cat'] = True
words['caterpillar'] = True
words['car'] = True
words['bar'] = True
words['exit'] = False

print('Start typing a word, "exit" to stop')
print('(Other words you might want to try: %s)\n' % ', '.join(sorted(
    k for k in words if k != 'exit')))

text = ''
while True:
    ch = getch()
    if ord(ch) < 32:
        print('Exiting')
        break

    text += ch
    value = words.get(text)
    if value is False:
        print('Exiting')
        break
    if value is not None:
        print(repr(text), 'is a word')
    if words.has_subtrie(text):
        print(repr(text), 'is a prefix of a word')
    else:
        print(repr(text), 'is not a prefix, going back to empty string')
        text = ''
