#!/usr/bin/python3
"""Example of ``pygtrie.CharTrie`` usage."""

__author__ = 'Michał Nazarewicz <mina86@mina86.com>'
__copyright__ = 'Copyright 2026 by Michał Nazarewicz'

# pylint: disable=missing-function-docstring

import os
import pathlib
import sys

try:
    import termios
    import tty

    def getch() -> str:
        """Reads single character from standard input."""
        attr = termios.tcgetattr(0)
        try:
            tty.setraw(0)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(0, termios.TCSADRAIN, attr)

except ImportError:
    try:
        from msvcrt import getch  # type: ignore[attr-defined,no-redef]  # pylint: disable=import-error
    except ImportError:
        sys.exit(0)

sys.path.insert(0, str(pathlib.Path(__file__).absolute().parent.parent))
import pygtrie  # pylint: disable=wrong-import-position


def noninteractive(dictionary: pygtrie.CharTrie[bool],
                   words: list[str]) -> None:
    """Prints out whether given dictionary contains given words (as words or
    prefixes)."""
    for word in words:
        if (value := dictionary.get(word)) is not None:
            print(f'{word}:', 'a valid word' if value else 'exit command')
        if dictionary.has_subtrie(word):
            print(f'{word}:', 'a prefix of a valid word')


def interactive(dictionary: pygtrie.CharTrie[bool]) -> None:
    """Interactively lets user type words letter-by-letter and checks whether
    the words are in the dictionary."""

    interesting = sorted(word
                         for word, is_continue in dictionary.iteritems()
                         if is_continue)
    print('Start typing a word; ‘exit’ to stop.')
    print('(Other words you might want to try:', ', '.join(interesting))

    text = ''
    while True:
        ch = getch()
        if ch in ('\r', '\n'):
            print('Clearing buffer, getting back to empty string')
            text = ''
            continue
        if ord(ch) < 32:
            break

        text += ch
        has_node = dictionary.has_node(text)  # has_node returns bitfield
        if not has_node:
            print(f'‘{text}’ is not a prefix or a word,'
                  ' going back to empty string')
            text = ''
        elif not has_node & pygtrie.Trie.HAS_VALUE:
            print(f'‘{text}’ is a prefix of a word')
        elif not dictionary[text]:
            print('Exit command entered, terminating')
            break
        elif has_node & pygtrie.Trie.HAS_SUBTRIE:
            print(f'‘{text}’ is a word and a prefix of a word')
        else:
            print(f'‘{text}’ is a word but not a prefix of a word,'
                  ' going back to empty string')
            text = ''


def main() -> None:
    print('Dictionary test\n'
          '===============\n')

    dictionary: pygtrie.CharTrie[bool] = pygtrie.CharTrie()
    dictionary['cat'] = True
    dictionary['caterpillar'] = True
    dictionary['car'] = True
    dictionary['bar'] = True
    dictionary['exit'] = False

    if os.isatty(0):
        interactive(dictionary)
    else:
        noninteractive(dictionary, ['cat', 'car', 'exit'])


if __name__ == '__main__':
    main()
