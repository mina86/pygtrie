Version History
---------------

2.6.2: 2026/09/14

- Optimise code and type annotations to reduce overhead introduced by
  the type hints in version 2.6.0.  Changes brought noticeable
  improvements compared to version 2.5.0:

  - Lookup of a non-existent key is 20–40% faster.  Prefer the
    :func:`~pygtrie.Trie.get` method to the subscription operator
    (i.e. ``trie[key]`` syntax) as it’s consistently faster.

  - Lookup of an existing key in a :class:`~pygtrie.StringTrie` is about
    20% faster.

  - Equality comparison between two tries of the same type, done either
    via the ``==`` operator or the :func:`~pygtrie.Trie.strictly_equals`
    method, is over 30% faster.

  - :func:`~pygtrie.Trie.prefixes`,
    :func:`~pygtrie.Trie.shortest_prefix` and
    :func:`~pygtrie.Trie.longest_prefix` methods are 30–40% faster.  On
    the flip side, :func:`~pygtrie.Trie.walk_towards` is about 5–15%
    slower.

  - Copying and merging tries is up to 10% faster.

  Unfortunately, some decrease in performance compared to v2.5.0 is
  still present.  Many operations are up to 5% slower.  Operations with
  larger change include:

  - :class:`~pygtrie.CharTrie` creation is about 20% slower.

  - Lookup of an existing key in a :class:`~pygtrie.CharTrie` via
    subscription operator (i.e. ``trie[key]`` syntax) is about 10%
    slower.  (Prefer :func:`~pygtrie.Trie.get` to avoid that slowdown).

  - Key deletion (i.e. ``del trie[key]`` operation) is up to 25% slower.
    :func:`~pygtrie.Trie.popitem` is up to 10% slower.

  - Pickling and unpickling a trie is about 20–30% slower.  (As a side
    note, `you should not be using pickle
    <https://mina86.com/2026/pickle-should-be-a-war-crime/>`_).

  Note that benchmarks used to arrive at those numbers aren’t
  particularly robust, and trie performance depends greatly on its
  structure.  Results may vary greatly depending on application.

  [Thanks to Dan Homola for reporting]

- Slices are no longer reported as existing in the trie.  Previously
  ``slice(some_key, None) in trie`` would always return true.  This was
  an unintended behaviour.  Now, such checks throw an exception.

- :func:`~pygtrie.Trie.merge` no longer throws :class:`~TypeError` when
  trying to merge a :class:`~pygtrie.StringTrie` into
  a :class:`~pygtrie.Trie`.

  Merging can lead to inconsistent state; the check tried to prevent it.
  However, it caught only one specific case.  Considering that the trie
  types can be subclassed, it’s not possible to predict all possible
  failures.

  Because of that, the explicit check was removed, and corner cases and
  possible failures were better documented.

- Add missing ``py.typed`` marker file which is required for type
  checkers to notice that the package contains type annotations.
  [Thanks to Avasam for reporting]

2.6.1: 2026/09/01

- Add ``python_requires`` metadata to indicate Python 3.11 requirement.
  [Thanks to skshetry for reporting]

2.6: 2026/09/01  [pulled back from PyPI]

- Python 3.11 is now required.  Users still on 3.10 need to hold off on
  upgrading till they switch to newer Python versions (3.10 is reaching
  end-of-life in a couple months) or temporarily vendor the module and
  replace all instances of ``_t.Self`` in ``pygtrie.py`` with
  ``_t.Any``.

- Add type annotations to the codebase.  This enables better static type
  analysis in codebases using pygtrie.

  There are a few corner cases where the type annotations aren’t
  entirely sound.  Most notably, the :class:`~pygtrie.Trie` class always
  returns keys as ``tuple[S, ...]`` regardless of declared type.  The
  documentation points out ways to deal with it.

  [Thanks to Dave Tapley and Avasam for requesting and discussing the
  feature]

- Deprecate and warn about some methods of :class:`~pygtrie._NoneStep`
  returned by :func:`~pygtrie.Trie.shortest_prefix` and
  :func:`~pygtrie.Trie.longest_prefix` when no prefix is found.

  Historically, prefixes were returned as ``(key, value)`` pairs and to
  maintain compatibility, lack of a prefix was signalled by a ``(None,
  None)`` pair.  However, treating lack of prefix as a tuple has long
  been deprecated:

      >>> result = CharTrie(foo=42).longest_prefix('bar')
      >>> key, value = result # Currently, (None, None);
      >>>                     # in the future, will raise TypeError.
      >>> key = result.key  # Currently None;
      >>>                   # in the future will raise AttributeError.
      >>> val = result.value  # Currently None;
      >>>                     # in the future will raise AttributeError.

  Truth value testing can be used to see whether a prefix exists, and
  the :func:`~pygtrie._NoneStep.get` method can be used to safely get the
  value of a prefix with a fallback if no prefix is found:

      >>> result = CharTrie(foo=42).longest_prefix('bar')
      >>> if result:
      ...     key = result.key
      ... else:
      ...     key = None
      >>> value = result.get(None)

  Behaviour when a prefix exists remains unchanged:

      >>> result = CharTrie(foo=42).longest_prefix('foobar')
      >>> key, value = result
      >>> assert (key, value) == ('foo', 42)
      >>> key, value = result.key, result.value
      >>> assert (key, value) == ('foo', 42)

- Add a deprecation warning to the :func:`~pygtrie._Step.set` method.
  :class:`~pygtrie._Step` is returned by methods such as
  :func:`~pygtrie.Trie.shortest_prefix` and
  :func:`~pygtrie.Trie.prefixes` and represents a valid prefix of a key.
  The method has been deprecated since version 2.3.3; it’ll now issue
  a warning when used.  The proper way to set the value of a prefix is
  via the ``value`` property, e.g.:

      >>> prefix = CharTrie(foo=0, foobar=0).longest_prefix('foobarbaz')
      >>> prefix.value += 1

- Fix :class:`~pygtrie._Step` string conversion raising an exception if
  a step represents a node without a value.  In previous versions the
  following would raise ``KeyError``:

      >>> list(map(repr, CharTrie(a=42).walk_towards('a')))
      ["('': <no value>)", "('a': 42)"]

- Remove obsolete license classifiers from the package metadata.
  [Thanks to Benjamin T. Schwertfeger for reporting]

2.5: 2022/07/16

- Add :func:`~pygtrie.Trie.merge` method which merges structures of two
  tries.

- Add :func:`~pygtrie.Trie.strictly_equals` method which compares two
  tries with stricter rules than the regular equality operator.  It’s
  not sufficient that keys and values are the same but the structure of
  the tries must be the same as well.  For example:

      >>> t0 = StringTrie({'foo/bar.baz': 42}, separator='/')
      >>> t1 = StringTrie({'foo/bar.baz': 42}, separator='.')
      >>> t0 == t1
      True
      >>> t0.strictly_equals(t1)
      False

- Fix :func:`~pygtrie.Trie.__eq__` implementation such that key values
  are taken into consideration rather than just looking at trie
  structure.  To see what this means it’s best to look at a few
  examples.  Firstly:

      >>> t0 = StringTrie({'foo/bar': 42}, separator='/')
      >>> t1 = StringTrie({'foo.bar': 42}, separator='.')
      >>> t0 == t1
      False

  This used to be true since the two tries have the same node
  structure.  However, as far as Mapping interface is concerned, they
  use different keys, i.e. ``set(t0) != set(t1)``.  Secondly:

      >>> t0 = StringTrie({'foo/bar.baz': 42}, separator='/')
      >>> t1 = StringTrie({'foo/bar.baz': 42}, separator='.')
      >>> t0 == t1
      True

  This used to be false since the two tries have different node
  structures (the first one splits the key into ``('foo', 'bar.baz')``
  while the second splits it into ``('foo/bar', 'baz')``).  However,
  their keys are the same, i.e. ``set(t0) == set(t1)``.  And lastly:

      >>> t0 = Trie({'foo': 42})
      >>> t1 = CharTrie({'foo': 42})
      >>> t0 == t1
      False

  This used to be true since the two tries have the same node
  structure.  However, the two classes return key as different types:
  :class:`~pygtrie.Trie` returns keys as tuples while
  :class:`~pygtrie.CharTrie` returns them as strings.

2.4.2: 2021/01/03

- Remove use of ``super`` in ``setup.py`` to fix compatibility with
  Python 2.7.  This changes build code only; no changes to the library
  itself.

2.4.1: 2020/11/20

- Remove dependency on ``packaging`` module from ``setup.py`` to fix
  installation on systems without that package.  This changes build
  code only; no changes to the library itself.  [Thanks to Eric
  McLachlan for reporting]

2.4.0: 2020/11/19  [pulled back from PyPI]

- Change ``children`` argument of the ``node_factory`` passed to
  :func:`~pygtrie.Trie.traverse` from a generator to an iterator with
  a custom bool conversion.  This allows checking whether node has
  children without having to iterate over them (``bool(children)``)

  To test whether this feature is available, one can check whether
  ``traverse.uses_bool_convertible_children`` property is true, e.g.:
  ``getattr(pygtrie.Trie.traverse, 'uses_bool_convertible_children',
  False)``.

  [Thanks to Pallab Pain for suggesting the feature]

2.3.3: 2020/04/04

- Fix ‘:class:`~AttributeError`: ``_NoChildren`` object has no attribute
  ``sorted_items``’ failure when iterating over a trie with sorting
  enabled.  [Thanks to Pallab Pain for reporting]

- Add ``value`` property setter to step objects returned by
  :func:`~pygtrie.Trie.walk_towards` et al.  This deprecates the
  ``set`` method.

- The module now exposes ``pygtrie.__version__`` making it possible to
  determine version of the library at run-time.

2.3.2: 2019/07/18

- Trivial metadata fix

2.3.1: 2019/07/18  [pulled back from PyPI]

- Fix :class:`~pygtrie.PrefixSet` initialisation incorrectly storing
  elements even if their prefixes are also added to the set.

  For example, ``PrefixSet(('foo', 'foobar'))`` incorrectly resulted
  in a two-element set even though the interface dictates that only
  ``foo`` is kept (recall that if ``foo`` is a member of the set,
  ``foobar`` is as well).  [Thanks to Tal Maimon for reporting]

- Fix the :func:`~pygtrie.Trie.copy` method not preserving the
  enable-sorting flag and, in the case of :class:`~pygtrie.StringTrie`,
  the ``separator`` property.

- Add support for the ``copy`` module so :func:`~copy.copy` can now be
  used with trie objects.

- Leaves and nodes with just one child use more memory-optimised
  representation which reduces overall memory usage of a trie
  structure.

- Minor performance improvement for adding new elements to
  a :class:`~pygtrie.PrefixSet`.

- Improvements to the string representation of objects, which now
  includes the type and, for a :class:`~pygtrie.StringTrie` object, the
  value of the separator property.

2.3: 2018/08/10

- New :func:`~pygtrie.Trie.walk_towards` method allows walking a path
  towards a node with a given key, accessing each step of the path.
  Compared to the ``walk_prefixes`` method, steps for nodes without
  assigned values are returned.

- Fix :func:`~pygtrie.PrefixSet.copy` not preserving type of backing
  trie.

- :class:`~pygtrie.StringTrie` now checks and explicitly rejects empty
  separators.  Previously, an empty separator would be accepted but lead
  to confusing errors later on.  [Thanks to Waren Long]

- Various documentation improvements, Python 2/3 compatibility and
  test coverage (python-coverage reports 100%).

2.2: 2017/06/03

- Fixes to ``setup.py`` breaking on Windows which prevents
  installation among other things.

2.1: 2017/03/23

- The library is now Python 3 compatible.

- The value returned by :func:`~pygtrie.Trie.shortest_prefix` and
  :func:`~pygtrie.Trie.longest_prefix` evaluates to false if no prefix
  was found.  This is in addition to it being a pair of ``None``\ s, of
  course.

2.0: 2016/07/06

- Sorting of child nodes is disabled by default for better
  performance.  The :func:`~pygtrie.Trie.enable_sorting` method can be
  used to bring back the old behaviour.

- Tries of arbitrary depth can be pickled without reaching Python’s
  recursion limits.  (N.B. The pickle format is incompatible with the
  one from the 1.2 release).  ``_Node``’s ``__getstate__`` and
  ``__setstate__`` methods can be used to implement other serialisation
  methods such as JSON.

1.2: 2016/06/21  [pulled back from PyPI]

- Tries can now be pickled.

- Iterating no longer uses recursion so tries of arbitrary depth can
  be iterated over.  The :func:`~pygtrie.Trie.traverse` method,
  however, still uses recursion thus cannot be used on big structures.

1.1: 2016/01/18

- Fix PyPI installation issues; all should work now.

1.0: 2015/12/16

- The module has been renamed from ``trie`` to ``pygtrie``.  This
  could break current users, but see the documentation for how to
  quickly upgrade your scripts.

- Add a :func:`~pygtrie.Trie.traverse` method which goes through the
  nodes of the trie, preserving the structure of the tree.  This is a
  depth-first traversal which can be used to search for elements or
  translate a trie into a different tree structure.

- Minor documentation fixes.

0.9.3: 2015/05/28

- Minor documentation fixes.

0.9.2: 2015/05/28

- Add Sphinx configuration and update docstrings to work better with
  Sphinx.

0.9.1: 2014/02/03

- New name.

0.9: 2014/02/03

- Initial release.
