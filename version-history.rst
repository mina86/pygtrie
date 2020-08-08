Version History
---------------

2.4.0: 2020/11/19

- Change ``children`` argument of the ``node_factory`` passed to
  :func:`Trie.traverse` from a generator to an iterator with a custom
  bool conversion.  This allows checking whether node has children
  without having to iterate over them (``bool(children)``)

  To test whether this feature is available, one can check whether
  :const:`Trie.traverse.uses_bool_convertible_children` property is
  true, e.g.: ``getattr(pygtrie.Trie.traverse,
  'uses_bool_convertible_children', False)``.

  [Thanks to Pallab Pain fo suggesting the feature]

2.3.3: 2020/04/04

- Fix to ‘:class:`AttributeError`: ``_NoChildren`` object has no
  attribute ``sorted_items``’ failure when iterating over a trie with
  sorting enabled.  [Thanks to Pallab Pain for reporting]

- Add ``value`` property setter to step objects returned by
  :func:`pygtrie.Trie.walk_towards` et al.  This deprecates the
  ``set`` method.

- The module now exports :const:`pygtrie.__version__` making it
  possible to determine version of the library at run-time.

2.3.2: 2019/07/18

- Trivial metadata fix

2.3.1: 2019/07/18  [pulled back from PyPi]

- Fix to :class:`pygtrie.PrefixSet` initialisation incorrectly storing
  elements even if their prefixes are also added to the set.

  For example, ``PrefixSet(('foo', 'foobar'))`` incorrectly resulted
  in a two-element set even though the interface dictates that only
  ``foo`` is kept (recall that if ``foo`` is member of the set,
  ``foobar`` is as well).  [Thanks to Tal Maimon for reporting]

- Fix to :func:`pygtrie.Trie.copy` method not preserving
  enable-sorting flag and, in case of :class:`pygtrie.StringTrie`,
  ``separator`` property.

- Add support for the ``copy`` module so :func:`copy.copy` can now be
  used with trie objects.

- Leafs and nodes with just one child use more memory-optimised
  representation which reduces overall memory usage of a trie
  structure.

- Minor performance improvement for adding new elements to
  a :class:`pygtrie.PrefixSet`.

- Improvements to string representation of objects which now includes
  type and, for :class:`pygtrie.StringTrie` object, value of separator
  property.

2.3: 2018/08/10

- New :func:`pygtrie.Trie.walk_towards` method allows walking a path
  towards a node with given key accessing each step of the path.
  Compared to :func:`pygtrie.Trie.walk_prefixes` method, steps for
  nodes without assigned values are returned.

- Fix to :func:`pygtrie.PrefixSet.copy` not preserving type of backing
  trie.

- :class:`pygtrie.StringTrie` now checks and explicitly rejects empty
  separators.  Previously empty separator would be accepted but lead
  to confusing errors later on.  [Thanks to Waren Long]

- Various documentation improvements, Python 2/3 compatibility and
  test coverage (python-coverage reports 100%).

2.2: 2017/06/03

- Fixes to ``setup.py`` breaking on Windows which prevents
  installation among other things.

2.1: 2017/03/23

- The library is now Python 3 compatible.

- Value returend by :func:`pygtrie.Trie.shortest_prefix` and
  :func:`pygtrie.Trie.longest_prefix` evaluates to false if no prefix was
  found.  This is in addition to it being a pair of `None`s of course.

2.0: 2016/07/06

- Sorting of child nodes is disabled by default for better
  performance.  :func:`pygtrie.Trie.enable_sorting` method can be used
  to bring back old behaviour.

- Tries of arbitrary depth can be pickled without reaching Python’s
  recursion limits.  (N.B. The pickle format is incompatible with one
  from 1.2 release).  ``_Node``’s ``__getstate__`` and ``__setstate__``
  method can be used to implement other serialisation methods such as
  JSON.

1.2: 2016/06/21  [pulled back from PyPI]

- Tries can now be pickled.

- Iterating no longer uses recursion so tries of arbitrary depth can
  be iterated over.  The :func:`pygtrie.Trie.traverse` method,
  however, still uses recursion thus cannot be used on big structures.

1.1: 2016/01/18

- Fixed PyPI installation issues; all should work now.

1.0: 2015/12/16

- The module has been renamed from ``trie`` to ``pygtrie``.  This
  could break current users but see documentation for how to quickly
  upgrade your scripts.

- Added :func:`pygtrie.Trie.traverse` method which goes through the
  nodes of the trie preserving structure of the tree.  This is
  a depth-first traversal which can be used to search for elements or
  translate a trie into a different tree structure.

- Minor documentation fixes.

0.9.3: 2015/05/28

- Minor documentation fixes.

0.9.2: 2015/05/28

- Added Sphinx configuration and updated docstrings to work better
  with Sphinx.

0.9.1: 2014/02/03

- New name.

0.9: 2014/02/03

- Initial release.
