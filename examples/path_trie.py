#!/usr/bin/python3
"""Example of subclassing ``pygtrie.Trie`` usage."""

__author__ = 'Michał Nazarewicz <mina86@mina86.com>'
__copyright__ = 'Copyright 2026 by Michał Nazarewicz'

# pylint: disable=missing-function-docstring

import contextlib
import os
import pathlib
import stat
import sys
import typing

sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent.parent))
import pygtrie  # pylint: disable=wrong-import-position


V = typing.TypeVar('V')

class PathTrie(pygtrie.Trie[pathlib.Path, V, str]):
    """A Trie whose keys are Path objects."""

    def _path_from_key(self, key: pathlib.Path) -> tuple[str, ...]:
        return key.parts

    def _key_from_path(self, path: typing.Iterable[str]) -> pathlib.Path:
        return pathlib.Path(*path)


ROOT_DIR = pathlib.Path('/usr/local')
SUB_DIRS = tuple(ROOT_DIR / d for d in ('lib', 'lib32', 'lib64', 'share'))
SUB_DIR = SUB_DIRS[0]


def list_sizes(root_dir: pathlib.Path) -> PathTrie[int]:
    """Recursively collects file sizes of files in given directory."""
    paths: PathTrie[int] = PathTrie()

    for dirname, unused_subdirs, filenames in os.walk(root_dir):
        dirpath = pathlib.Path(dirname)
        for filename in filenames:
            fullpath = dirpath / filename
            with contextlib.suppress(OSError):
                filestat = fullpath.stat()
                if stat.S_IFMT(filestat.st_mode) == stat.S_IFREG:
                    paths[fullpath] = filestat.st_size

    return paths


def print_info(paths: PathTrie[int]) -> None:
    """Prints some information about collected file sizes."""
    # Size of all files we've scanned
    print(f'Size of {ROOT_DIR}:', sum(paths.itervalues()))

    # Size of all files of a sub-directory
    if paths.has_node(SUB_DIR):
        print(f'Size of {SUB_DIR}:', sum(paths.itervalues(prefix=SUB_DIR)))

    # Check existence of some directories
    for directory in SUB_DIRS:
        if paths.has_subtrie(directory):
            print(directory, 'exists')
        else:
            print(directory, 'does not exist')


def main() -> None:
    print('Storing file information in the trie\n'
          '====================================\n')

    paths = list_sizes(ROOT_DIR)
    print_info(paths)

    print('\nAfter excluding', SUB_DIR)
    del paths[SUB_DIR:]
    print_info(paths)


if __name__ == '__main__':
    main()
