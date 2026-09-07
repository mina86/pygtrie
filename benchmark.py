#!/usr/bin/env python3
"""Benchmarks for the pygtrie module.

Runs a battery of timing comparisons between pygtrie's trie types (``CharTrie``,
``Trie``, ``PrefixSet``) and the built-in ``dict``/``set``, using real-world-ish
text corpora as input.

By default this looks for ``*.txt.lzma`` files under ``testdata`` directory.
Usage::

    python3 benchmark.py
    python3 benchmark.py --repeat 9 testdata/kordian.txt.lzma
    python3 benchmark.py --sample-size 20000 --ngram 3
"""

# pylint: disable=missing-class-docstring,missing-function-docstring

import argparse
import dataclasses
import lzma
import pathlib
import pickle
import random
import re
import statistics
import string
import sys
import timeit
import typing

import pygtrie


TESTDATA_DIR = pathlib.Path('testdata')
REPEAT: int = 5


T = typing.TypeVar('T')


#### Corpus loading


def list_test_files(path: pathlib.Path) -> list[pathlib.Path]:
    return [path
            for path in sorted(path.iterdir())
            if path.is_file() and not path.name.startswith('.')]


@dataclasses.dataclass(init=False)
class Corpus:
    words: typing.Sequence[str]
    unique: typing.Sequence[str]
    samples: typing.Sequence[str]
    missing: typing.Sequence[str]
    d: dict[str, int]  # pylint: disable=invalid-name
    t: pygtrie.CharTrie[int]  # pylint: disable=invalid-name

    def __init__(self,
                 path: pathlib.Path,
                 sample_size: int,
                 rng: random.Random) -> None:
        self.words = self.__load_corpus(path)
        self.unique = tuple(
            dict.fromkeys(self.words))  # preserve first-seen order
        sample_size = min(sample_size, len(self.unique))
        self.samples = tuple(rng.sample(self.unique, sample_size))
        self.misses = self.__make_negative_samples(
            self.unique, sample_size, rng)
        self.d = self.make_dict()
        self.t = self.make_trie()
        assert self.t == self.d

    def __make_items(self) -> typing.Iterable[tuple[str, int]]:
        return ((word, idx) for idx, word in enumerate(self.unique))

    def make_dict(self) -> dict[str, int]:
        return dict(self.__make_items())

    def make_trie(self) -> pygtrie.CharTrie[int]:
        return pygtrie.CharTrie(self.__make_items())

    def make_trie_all(self) -> dict[str, int]:
        return {word: idx for idx, word in enumerate(self.words)}

    @classmethod
    def __load_corpus(cls, path: pathlib.Path) -> typing.Sequence[str]:
        """Decompresses ``path`` and splits it into lowercase word tokens."""
        with lzma.open(path, 'rt', encoding='utf-8') as rd:
            text = rd.read()
        return tuple(word.lower()
                     for word in re.findall(r'\w+', text, re.UNICODE))

    @classmethod
    def __make_negative_samples(cls,
                                vocabulary: typing.Sequence[str],
                                count: int,
                                rng: random.Random) -> typing.Sequence[str]:
        """Returns ``count`` words that aren’t in the vocabulary."""
        vocab_set = frozenset(vocabulary)
        out: list[str] = []
        attempts = 0
        while len(out) < count and attempts < count * 10:
            attempts += 1
            word = rng.choice(vocabulary) + rng.choice(string.ascii_lowercase)
            if word not in vocab_set:
                out.append(word)
        return tuple(out)


##### Timing harness


@dataclasses.dataclass(frozen=True)
class Result:
    name: str
    mean: float
    n_ops: int


def bench(
        name: str,
        func: typing.Callable[[],typing.Any] | typing.Callable[[T],typing.Any],
        *,
        setup: typing.Callable[[], T] | None=None,
        n_ops: int,
) -> Result:
    """Times ``func()`` discarding its return value."""
    stmt: 'str' | typing.Callable[[], typing.Any]
    if setup is None:
        globs = {}
        stmt = typing.cast(typing.Callable[[], typing.Any], func)
        init = 'pass'
    else:
        stmt, init = 'func(data)', 'data = setup()'
        globs = {'func': func, 'setup': setup}
    mean = statistics.mean(
        timeit.timeit(stmt, init, number=1, globals=globs)
        for _ in range(REPEAT)
    )
    return Result(name, mean, n_ops)


def fmt_seconds(sec: float) -> str:
    if sec < 1e-6:
        return f'{sec * 1e9:8.1f} ns'
    if sec < 1e-3:
        return f'{sec * 1e6:8.1f} µs'
    if sec < 1:
        return f'{sec * 1e3:8.2f} ms'
    return f'{sec:8.3f}  s'


def print_results(title: str, results: typing.Iterable[Result]) -> None:
    print(f'\n-- {title} --')
    for r in results:
        mean = fmt_seconds(r.mean)
        line = f'  {r.name:<32} mean={mean}'
        if r.n_ops > 1:
            line += f'   ({fmt_seconds(r.mean / r.n_ops)}/op, n={r.n_ops})'
        print(line)


##### Individual benchmark sections


def bench_construction(words: typing.Sequence[str]) -> list[Result]:
    n = len(words)

    def build_dict() -> dict[str, int]:
        d: dict[str, int] = {}
        for i, w in enumerate(words):
            d[w] = i
        return d

    def build_trie() -> pygtrie.CharTrie[int]:
        t: pygtrie.CharTrie[int] = pygtrie.CharTrie()
        for i, w in enumerate(words):
            t[w] = i
        return t

    def build_trie_from_iterator() -> pygtrie.CharTrie[int]:
        return pygtrie.CharTrie((w, i) for i, w in enumerate(words))

    def build_trie_fromkeys() -> pygtrie.CharTrie[int]:
        return pygtrie.CharTrie.fromkeys(words, 0)

    return [
        bench('dict (assign one by one)', build_dict, n_ops=n),
        bench('CharTrie (assign one by one)', build_trie, n_ops=n),
        bench('CharTrie (from iterator)', build_trie_from_iterator, n_ops=n),
        bench('CharTrie.fromkeys', build_trie_fromkeys, n_ops=n),
    ]


def bench_lookup(cps: Corpus, samples: typing.Sequence[str]) -> list[Result]:
    n = len(samples)

    def getitem(container: dict[str, int] | pygtrie.CharTrie[int]) -> int:
        found = 0
        get = container.__getitem__
        for word in samples:
            try:
                found += get(word)
            except KeyError:
                pass
        return found

    def get(container: dict[str, int] | pygtrie.CharTrie[int]) -> int:
        get = container.get
        return sum(get(word, 0) for word in samples)

    return [
        bench('dict[key] (try/except)',
              getitem, setup=lambda: cps.d, n_ops=n),
        bench('Trie[key] (try/except)',
              getitem, setup=lambda: cps.t, n_ops=n),
        bench('Trie.get(key)',
              get, setup=lambda: cps.t, n_ops=n),
    ]


def bench_iteration(cps: Corpus) -> list[Result]:
    return [
        bench('dict: list(items())',
              lambda: list(cps.d.items()), n_ops=len(cps.d)),
        bench('CharTrie: items()', cps.t.items, n_ops=len(cps.t)),
        bench('CharTrie: len()', lambda: len(cps.t), n_ops=len(cps.t)),
    ]


def bench_equals(cps: Corpus) -> list[Result]:
    n = len(cps.unique)

    def do_assert(result: bool) -> None:
        assert result

    return [
        bench('CharTrie == dict', lambda: do_assert(cps.t == cps.d), n_ops=n),
        bench('CharTrie == CharTrie',
              func=lambda other: do_assert(cps.t == other),
              setup=cps.t.copy,
              n_ops=n),
        bench('CharTrie.strictly_equals',
              func=lambda other: do_assert(cps.t.strictly_equals(other)),
              setup=cps.t.copy,
              n_ops=n),
    ]

def bench_prefix_ops(cps: Corpus) -> list[Result]:
    prefixes = list(dict.fromkeys(word[:max(1, len(word) // 2)]
                                  for word in cps.samples))

    def has_subtrie() -> int:
        has_subtrie = cps.t.has_subtrie
        return sum(has_subtrie(prefix) for prefix in prefixes)

    def longest_prefix() -> int:
        longest_prefix = cps.t.longest_prefix
        return sum(bool(longest_prefix(prefix)) for prefix in prefixes)

    def iter_prefixes_all() -> int:
        func = cps.t.prefixes
        return sum(1 for word in cps.samples for _ in func(word))

    return [
        bench('has_subtrie(prefix)', has_subtrie,       n_ops=len(prefixes)),
        bench('longest_prefix(prefix)', longest_prefix, n_ops=len(prefixes)),
        bench('prefixes(word) walk', iter_prefixes_all, n_ops=len(cps.samples)),
    ]


def bench_deletion(cps: Corpus) -> list[Result]:

    def delete(container: dict[str, int] | pygtrie.CharTrie[int]) -> None:
        delete = container.__delitem__
        for word in cps.unique:
            delete(word)

    def popall(container: dict[str, int] | pygtrie.CharTrie[int]) -> None:
        pop = container.popitem
        try:
            while pop():
                pass
        except KeyError:
            pass

    return [
        bench('dict: delete all keys',
              delete, setup=cps.make_dict, n_ops=len(cps.unique)),
        bench('dict: popitem() until empty',
              popall, setup=cps.make_dict, n_ops=len(cps.unique)),
        bench('CharTrie: delete all keys',
              delete, setup=cps.make_trie, n_ops=len(cps.unique)),
        bench('CharTrie: popitem() until empty',
              popall, setup=cps.make_trie, n_ops=len(cps.unique)),
    ]


def bench_copy_and_merge(cps: Corpus) -> list[Result]:
    n = len(cps.unique)

    Pair = tuple[pygtrie.CharTrie[int], pygtrie.CharTrie[int]]

    def prepare_halfs() -> Pair:
        tries: Pair = [pygtrie.CharTrie(), pygtrie.CharTrie()]
        for i, word in enumerate(cps.words):
            tries[i % 2][word] = i
        return tries

    def merge(tries: Pair) -> None:
        dst, src = tries
        dst.merge(src)

    return [
        bench('dict.copy()', cps.d.copy, n_ops=n),
        bench('CharTrie.copy()', cps.t.copy, n_ops=n),
        bench('CharTrie.merge()', merge, setup=prepare_halfs, n_ops=n//2),
    ]



def bench_pickle(cps: Corpus) -> list[Result]:
    n = len(cps.unique)
    return [
        bench("pickle.dumps(dict)", lambda: pickle.dumps(cps.d), n_ops=n),
        bench("pickle.loads(dict)",
              func=pickle.loads, setup=lambda: pickle.dumps(cps.d), n_ops=n),
        bench("pickle.dumps(CharTrie)", lambda: pickle.dumps(cps.t), n_ops=n),
        bench("pickle.loads(CharTrie)",
              func=pickle.loads, setup=lambda: pickle.dumps(cps.t), n_ops=n),
    ]


##### Main


def run_corpus(path: pathlib.Path,
               sample_size: int,
               rng: random.Random) -> None:
    print(f'\n{'=' * 72}\nCorpus: {path}')
    cps = Corpus(path, sample_size, rng)

    print(f'  words: {len(cps.words):,} total,'
          f' {len(cps.unique):,} unique')
    for name, lst in (('samples', cps.samples), ('misses', cps.misses)):
        if len(lst) == 1:
            formatted = f'‘{lst[0]}’'
        elif len(lst) <= 10:
            joined = ',’ ‘'.join(lst[:-1])
            formatted = f'‘{joined}’ and ‘{lst[-1]}’'
        else:
            joined = ',’ ‘'.join(lst[:10])
            formatted = f'‘{joined}’, …'
        print(f'  ex. {name}: {formatted}')

    print_results('Construction (all words)',    bench_construction(cps.words))
    print_results('Construction (unique words)', bench_construction(cps.unique))
    print_results('Lookup (hits)',   bench_lookup(cps, cps.samples))
    print_results('Lookup (misses)', bench_lookup(cps, cps.misses))
    print_results('Full iteration', bench_iteration(cps))
    print_results('Equality', bench_equals(cps))
    print_results('Prefix operations', bench_prefix_ops(cps))
    print_results('Deletion', bench_deletion(cps))
    print_results('Copy & Merge', bench_copy_and_merge(cps))
    print_results('Pickle round-trip', bench_pickle(cps))


def posint(arg: str) -> int:
    num = int(arg)
    if num <= 0:
        raise ValueError('expected positive integer')
    return num


def main(argv: typing.Sequence[str] | None=None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.replace('``', '`'),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('FILE', nargs='*', type=pathlib.Path,
                        help=('lzma-compressed text file to benchmark.'
                              '  Defaults to the files under testdata.'))
    parser.add_argument('--repeat', type=posint, default=5,
                        help=('Number of times to repeat each timing;'
                              ' default: 5'))
    parser.add_argument('--sample-size', type=posint, default=5000,
                        help=('Number of words to sample for lookup/prefix'
                              ' benchmarks; default: 5000'))
    parser.add_argument('--seed', type=int, default=0,
                        help='random seed, for reproducible sampling')
    args = parser.parse_args(argv)

    global REPEAT  # pylint: disable=global-statement
    REPEAT = args.repeat

    print(f'pygtrie version: {getattr(pygtrie, '__version__', 'unknown')}')
    print(f'python version: {sys.version.split()[0]}')

    files = args.FILE or list_test_files(TESTDATA_DIR)
    for path in files:
        run_corpus(path, args.sample_size, random.Random(args.seed))

    print(f'\n{'=' * 72}\nDone.')


if __name__ == '__main__':
    main()
