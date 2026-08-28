# -*- coding: utf-8 -*-
"""Pure Python implementation of a trie data structure.

`Trie data structure <http://en.wikipedia.org/wiki/Trie>`_, also known as radix
or prefix tree, is a tree associating keys to values where all the descendants
of a node have a common prefix (associated with that node).

The trie module contains :class:`pygtrie.Trie`, :class:`pygtrie.CharTrie` and
:class:`pygtrie.StringTrie` classes each implementing a mutable mapping
interface, i.e. :class:`dict` interface.  As such, in most circumstances,
:class:`pygtrie.Trie` could be used as a drop-in replacement for
a :class:`dict`, but the prefix nature of the data structure is trie’s real
strength.

The module also contains :class:`pygtrie.PrefixSet` class which uses a trie to
store a set of prefixes such that a key is contained in the set if it or its
prefix is stored in the set.

Features
--------

- A full mutable mapping implementation.

- Supports iterating over as well as deleting of a branch of a trie
  (i.e. subtrie)

- Supports prefix checking as well as shortest and longest prefix
  look-up.

- Extensible for any kind of user-defined keys.

- A PrefixSet supports “all keys starting with given prefix” logic.

- Can store any value including None.

For a few simple examples see ``example.py`` file.
"""

__author__ = 'Michał Nazarewicz <mina86@mina86.com>'
__copyright__ = ('Copyright 2014-2017 Google LLC',
                 'Copyright 2018-2026 Michał Nazarewicz <mina86@mina86.com>')
# __version__ = '' # set by setup.py sdist or build


import copy as _copy
import collections.abc as _abc
import warnings as _warnings
import types as _types
import typing as _t


K = _t.TypeVar('K')
V = _t.TypeVar('V')
S = _t.TypeVar('S')
T = _t.TypeVar('T')


class _MakeCopy(_t.Protocol):  # pylint: disable=too-few-public-methods
    """A callable which copies (or otherwise maps) a value to itself.

    This is used both to copy trie’s steps and trie’s values, hence the argument
    and return type are described by a method-scoped type variable rather than
    the module-level ``V`` so a single ``_MakeCopy`` object can be called with
    different (unrelated) types over the course of a copy.
    """

    def __call__(self, value: T) -> T: ...


class ShortKeyError(KeyError):
    """Raised when given key is a prefix of an existing longer key
    but does not have a value associated with itself."""


class _NoCopy:
    """Object which returns itself when copying."""
    __slots__ = ()
    def __copy__(self) -> _t.Self:
        return self
    def __deepcopy__(self, memo: _t.Any) -> _t.Self:
        return self


# Sentinel used as default value in function arguments.
_Sentinel = _t.NewType('_Sentinel', _NoCopy)
_SENTINEL = _Sentinel(_NoCopy())

def _is_not_sentinel(value: T | _Sentinel) -> _t.TypeGuard[T]:
    return value is not _SENTINEL

# Sentinel indicating node has no value.
_NoValue = _t.NewType('_NoValue', _NoCopy)
_NOVAL = _NoValue(_NoCopy())

def _is_value(value: V | _NoValue) -> _t.TypeGuard[V]:
    return value is not _NOVAL


class _FalsyIterator(_NoCopy):
    """An empty iterator which is in addition falsy."""
    __slots__ = ()

    def __new__(cls) -> _t.Self:
        # pylint: disable=no-member
        return cls.__instance  # type: ignore

    def __bool__(self) -> _t.Literal[False]:
        return False
    def __iter__(self) -> _t.Self:
        return self
    def __next__(self) -> _t.Never:
        raise StopIteration

_FalsyIterator._FalsyIterator__instance = (  # type: ignore[attr-defined]  # pylint: disable=protected-access
    object().__new__(_FalsyIterator))  # pylint: disable=no-value-for-parameter


class _AnyChildren(_t.Protocol[S, V]):
    """Protocol for node’s children.  Covers cases with no children and with
    children."""

    def __bool__(self) -> bool:
        """Returns whether there are any children."""

    def __len__(self) -> int:
        """Returns number of children."""

    def items(self) -> _t.Iterable[tuple[S, '_Node[S, V]']]:
        """Iterates over all children as ``(step, node)`` tuples."""

    def sorted_items(self) -> _t.Iterable[tuple[S, '_Node[S, V]']]:
        """Iterates over all children as ``(step, node)`` tuples in sorted
        order."""

    def get(self, step: S) -> _t.Union['_Node[S, V]', None]:
        """Returns child at given step, or ``None`` if missing."""

    def add(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        """Adds a child at given step; returns the new node.

        ``parent`` must be the ``_Node`` object which owns this object.  In some
        situations, adding of a child will change the ``parent.children``
        object.
        """

    def require(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        """Adds a child at given step if missing; returns existing or the new
        node.

        ``parent`` must be the ``_Node`` object which owns this object.  In some
        situations, adding of a child will change the ``parent.children``
        object.
        """

    def merge(self,
              other: '_AnyChildren[S, V]',
              queue: list[tuple['_Node[S, V]', '_Node[S, V]']],
              ) -> '_AnyChildren[S, V]':
        """Moves nodes from ``other`` into this object and returns new container
        with all the children.

        The correct usage of the method is::

            parent.children = parent.children.merge(other.children, queue)
            other.children = _NoChildren()
        """

    def copy(self,
             make_copy: _MakeCopy,
             queue: list[_t.Iterable['_Node[S, V]']]) -> _t.Self:
        """Recursively copies the current object.  ``make_copy`` is used to copy
        the step and value objects."""

    def pick(self) -> tuple[S, '_Node[S, V]']:
        """Picks arbitrary child.

        Not implemented in :class:`pygtrie._NoChildren`.
        """

    def delete(self, parent: '_Node[S, V]', step: S) -> None:
        """Delets specified child.  ``stup`` **must** be existing step.

        Not implemented in :class:`pygtrie._NoChildren`.
        """


class _NoChildren(_AnyChildren[S, V], _NoCopy):
    """Collection representing lack of any children."""
    __slots__ = ()

    def __new__(cls) -> _t.Self:
        # pylint: disable=no-member
        return cls.__instance  # type: ignore

    def __bool__(self) -> _t.Literal[False]:
        return False
    def __len__(self) -> _t.Literal[0]:
        return 0

    def items(self) -> tuple[()]:
        return ()
    sorted_items = items

    def get(self, step: S) -> None:
        return None

    def add(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        node: _Node[S, V] = _Node()
        parent.children = _OneChild(step, node)
        return node

    require = add

    def merge(self,
              other: '_AnyChildren[S, V]',
              queue: list[tuple['_Node[S, V]', '_Node[S, V]']],
              ) -> '_AnyChildren[S, V]':
        return other

    def copy(self,
             make_copy: _MakeCopy,
             queue: list[_t.Iterable['_Node[S, V]']]) -> _t.Self:
        return self

    def pick(self) -> tuple[S, '_Node[S, V]']:
        raise NotImplementedError()

    def delete(self, parent: '_Node[S, V]', step: S) -> None:
        raise NotImplementedError()

_NoChildren._NoChildren__instance = (  # type: ignore[attr-defined]  # pylint: disable=protected-access
    object().__new__(_NoChildren))  # pylint: disable=no-value-for-parameter


class _OneChild(_AnyChildren[S, V]):
    """Children collection representing a single child."""
    __slots__ = ('step', 'node')

    step: S
    node: '_Node[S, V]'

    def __init__(self, step: S, node: '_Node[S, V]') -> None:
        self.step = step
        self.node = node

    def __bool__(self) -> _t.Literal[True]:
        return True
    def __len__(self) -> _t.Literal[1]:
        return 1

    def items(self) -> tuple[tuple[S, '_Node[S, V]']]:
        return ((self.step, self.node),)
    sorted_items = items

    def pick(self) -> tuple[S, '_Node[S, V]']:
        return (self.step, self.node)

    def get(self, step: S) -> _t.Union['_Node[S, V]', None]:
        return self.node if step == self.step else None

    def add(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        node: _Node[S, V]  = _Node()
        parent.children = _Children((self.step, self.node), (step, node))
        return node

    def require(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        return self.node if self.step == step else self.add(parent, step)

    def merge(self,
              other: '_AnyChildren[S, V]',
              queue: list[tuple['_Node[S, V]', '_Node[S, V]']],
              ) -> '_AnyChildren[S, V]':
        # pylint: disable=unidiomatic-typecheck
        if type(other) == _OneChild and other.step == self.step:
            queue.append((self.node, other.node))
            return self
        elif other:
            children: _Children[S, V] = _Children((self.step, self.node))
            children.merge(other, queue)
            return children
        else:
            return self

    def delete(self, parent: '_Node[S, V]', step: S) -> None:
        parent.children = _NoChildren()

    def copy(self,
             make_copy: _MakeCopy,
             queue: list[_t.Iterable['_Node[S, V]']]) -> '_OneChild[S, V]':
        cpy = _OneChild(make_copy(self.step), self.node.shallow_copy(make_copy))
        queue.append((cpy.node,))
        return cpy


class _Children(_AnyChildren[S, V]):
    """Children collection representing more than one child."""

    __slots__ = ('_nodes',)
    _nodes: dict[S, '_Node[S, V]']

    def __init__(self, *items: tuple[S, '_Node[S, V]']) -> None:
        self._nodes = dict(items)

    def __bool__(self) -> _t.Literal[True]:
        return True
    def __len__(self) -> int:
        return len(self._nodes)

    def items(self) -> _t.Iterable[tuple[S, '_Node[S, V]']]:
        return self._nodes.items()

    def sorted_items(self) -> list[tuple[S, '_Node[S, V]']]:
        return sorted(self._nodes.items())

    def pick(self) -> tuple[S, '_Node[S, V]']:
        return next(iter(self._nodes.items()))

    def get(self, step: S) -> _t.Union['_Node[S, V]', None]:
        return self._nodes.get(step)

    def __getitem__(self, step: S) -> '_Node[S, V]':
        return self._nodes[step]

    def add(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        node: '_Node[S, V]' = _Node()
        self._nodes[step] = node
        return node

    def require(self, parent: '_Node[S, V]', step: S) -> '_Node[S, V]':
        return self._nodes.setdefault(step, _Node())

    def merge(self,
              other: '_AnyChildren[S, V]',
              queue: list[tuple['_Node[S, V]', '_Node[S, V]']],
    ) -> _t.Self:
        for step, other_node in other.items():
            node = self._nodes.setdefault(step, other_node)
            if node is not other_node:
                queue.append((node, other_node))
        return self

    def delete(self, parent: '_Node[S, V]', step: S) -> None:
        del self._nodes[step]
        if len(self) == 1:
            parent.children = _OneChild(*self._nodes.popitem())

    def copy(self,
             make_copy: _MakeCopy,
             queue: list[_t.Iterable['_Node[S, V]']]) -> '_Children[S, V]':
        # pylint: disable=protected-access
        cpy: _Children[S, V] = _Children()
        cpy._nodes.update((make_copy(step), node.shallow_copy(make_copy))
                         for step, node in self.items())
        queue.append(cpy._nodes.values())
        return cpy


class _Node(_t.Generic[S, V]):
    """A single node of a trie.

    Stores value associated with the node and dictionary of children.
    """
    __slots__ = ('children', 'value')

    children: _AnyChildren[S, V]
    value: V | _NoValue

    def __init__(self) -> None:
        self.children = _NoChildren()
        self.value = _NOVAL

    def merge(self, other: '_Node[S, V]', overwrite: bool) -> None:
        """Move children from other node into this one.

        Args:
            other: Other node to move children and value from.
            overwrite: Whether to overwrite existing node values.
        """
        queue: list[tuple[_Node[S, V], _Node[S, V]]] = [(self, other)]
        while queue:
            lhs, rhs = queue.pop()
            if lhs.value is _NOVAL or (overwrite and rhs.value is not _NOVAL):
                lhs.value = rhs.value
            lhs.children = lhs.children.merge(rhs.children, queue)
            rhs.children = _NoChildren()

    def iterate(self,
                path: list[S],
                shallow: bool,
                items: _t.Callable[[_AnyChildren[S, V]],
                                   _t.Iterable[tuple[S, '_Node[S, V]']]],
    ) -> _t.Iterator[tuple[list[S], V]]:
        """Yields all the nodes with values associated to them in the trie.

        Args:
            path: Path leading to this node.  Used to construct the key when
                returning value of this node and as a prefix for children.
            shallow: Perform a shallow traversal, i.e. do not yield nodes if
                their prefix has been yielded.
            items: A callable which takes ``node.children`` as a sole argument
                and returns an iterable of children as ``(step, node)`` pairs.
                It would typically call ``items`` or ``sorted_items`` method on
                the argument depending on whether sorted output is desired.

        Yields:
            ``(path, value)`` tuples.
        """
        # Use iterative function with stack on the heap so we don't hit Python's
        # recursion depth limits.
        node = self
        stack = []
        while True:
            if _is_value(value := node.value):
                yield (path, value)

            if (not shallow or node.value is _NOVAL) and node.children:
                stack.append(iter(items(node.children)))
                # None value will be overridden by `path[-1] = step` below so
                # it’s alright to temporarily add None.
                path.append(None)  # type: ignore

            while True:
                try:
                    step, node = next(stack[-1])
                    path[-1] = step
                    break
                except StopIteration:
                    stack.pop()
                    path.pop()
                except IndexError:
                    return

    def traverse(self,
                 node_factory: _t.Callable[..., T],
                 path_conv: _t.Callable[[tuple[S, ...]], _t.Any],
                 path: list[S],
                 items: _t.Callable[[_AnyChildren[S, V]],
                                    _t.Iterable[tuple[S, '_Node[S, V]']]],
    ) -> T:
        """Traverses the node and returns another type of node from factory.

        Args:
            node_factory: Callable to construct return value.
            path_conv: Callable to convert node path to a key.
            path: Current path for this node.
            items: A callable which takes ``node.children`` as a sole argument
                and returns an iterable of children as ``(step, node)`` pairs.
                It would typically call ``items`` or ``sorted_items`` method on
                the argument depending on whether sorted output is desired.

        Returns:
            An object constructed by calling node_factory(path_conv, path,
            children, value=...), where children are constructed by node_factory
            from the children of this node.  There doesn't need to be 1:1
            correspondence between original nodes in the trie and constructed
            nodes (see make_test_node_and_compress in test.py).
        """
        children: _t.Iterable[T]
        if self.children:
            children = (
                node.traverse(node_factory, path_conv, path + [step], items)
                for step, node in items(self.children))
        else:
            children = _FalsyIterator()

        value = self.value
        value_maybe = () if value is _NOVAL else (value,)

        return node_factory(path_conv, tuple(path), children, *value_maybe)

    def equals(self, other: '_Node[S, V]') -> bool:
        """Returns whether this and other node are recursively equal."""
        # Like iterate, we don't recurse so this works on deep tries.
        a: _Node[S, V] = self
        b: _Node[S, V] = other
        stack: list[tuple[
            _t.Iterator[tuple[S, _Node[S, V]]],
            _Children[S, V]
        ]] = []
        while True:
            if a.value != b.value or len(a.children) != len(b.children):
                return False
            # len(a.children) == len(b.children) implies they are the same type.

            # Just one child.  Handle without recursion.
            if len(a.children) == 1:
                ac = _t.cast(_OneChild[S, V], a.children)
                bc = _t.cast(_OneChild[S, V], b.children)
                if ac.step != bc.step:
                    return False
                a, b = ac.node, bc.node
                continue

            # Multiple children.  Append to stack.
            if a.children:
                stack.append((iter(a.children.items()),
                              _t.cast(_Children[S, V], b.children)))

            while True:
                try:
                    key, a = next(stack[-1][0])
                    b = stack[-1][1][key]
                    break
                except StopIteration:
                    stack.pop()
                except IndexError:
                    return True
                except KeyError:
                    return False

    __hash__ = None  # type: ignore[assignment]
    __bool__ = None

    def shallow_copy(self, make_copy: _MakeCopy) -> '_Node[S, V]':
        """Returns a copy of the node which shares the children property."""
        cpy: _Node[S, V] = _Node()
        cpy.children = self.children
        cpy.value = make_copy(self.value)
        return cpy

    def copy(self, make_copy: _MakeCopy) -> '_Node[S, V]':
        """Returns a copy of the node structure."""
        cpy = self.shallow_copy(make_copy)
        queue: list[_t.Iterable['_Node[S, V]']] = [(cpy,)]
        while queue:
            for node in queue.pop():
                node.children = node.children.copy(make_copy, queue)
        return cpy

    def __getstate__(self) -> list[int | S | V]:
        """Get state used for pickling.

        The state is encoded as a list of simple commands which consist of an
        integer and some command-dependent number of arguments.  The commands
        modify what the current node is by navigating the trie up and down and
        setting node values.  Possible commands are:

        * [n, step0, step1, ..., stepn-1, value], for n >= 0, specifies step
          needed to reach the next current node as well as its new value.  There
          is no way to create a child node without setting its (or its
          descendant's) value.

        * [-n], for -n < 0, specifies to go up n steps in the trie.

        When encoded as a state, the commands are flattened into a single list.

        For example::

            [ 0, 'Root',
              2, 'Foo', 'Bar', 'Root/Foo/Bar Node',
             -1,
              1, 'Baz', 'Root/Foo/Baz Node',
             -2,
              1, 'Qux', 'Root/Qux Node' ]

        Creates the following hierarchy::

            -* value: Root
             +-- Foo --* no value
             |         +-- Bar -- * value: Root/Foo/Bar Node
             |         +-- Baz -- * value: Root/Foo/Baz Node
             +-- Qux -- * value: Root/Qux Node

        Returns:
            A pickable state which can be passed to :func:`_Node.__setstate__`
            to reconstruct the node and its full hierarchy.
        """
        # Like iterate, we don't recurse so pickling works on deep tries.
        state: list[int | S | V] = [] if self.value is _NOVAL else [0]
        last_cmd = 0
        node: _Node[S, V] = self
        stack: list[_t.Iterator[tuple[S, '_Node[S, V]']]] = []
        while True:
            if node.value is not _NOVAL:
                last_cmd = 0
                state.append(_t.cast(V, node.value))
            stack.append(iter(node.children.items()))

            while True:
                try:
                    step, node = next(stack[-1])
                    break
                except StopIteration:
                    if last_cmd < 0:
                        state[-1] = _t.cast(int, state[-1]) - 1
                    else:
                        last_cmd = -1
                        state.append(-1)
                    stack.pop()
                    if not stack:
                        state.pop()  # Final -n command is not necessary
                        return state

            if last_cmd > 0:
                last_cmd += 1
                state[-last_cmd] = _t.cast(int, state[-last_cmd]) + 1
            else:
                last_cmd = 1
                state.append(1)
            state.append(step)

    def __setstate__(self, state: list[int | S | V]) -> None:
        """Unpickles node.  See :func:`_Node.__getstate__`."""
        self.__init__()  # type: ignore[misc]
        it = iter(state)
        stack: list[_Node[S, V]] = [self]
        for raw_cmd in it:
            cmd = _t.cast(int, raw_cmd)
            if cmd < 0:
                del stack[cmd:]
            else:
                while cmd > 0:
                    parent = stack[-1]
                    step = _t.cast(S, next(it))
                    stack.append(parent.children.add(parent, step))
                    cmd -= 1
                stack[-1].value = _t.cast(V, next(it))


class _NoneStep:
    """Representation of a non-existent step towards non-existent node.

    The class is private because it should not be constructed by external
    code.  Objects of this type are returned by :class:`Trie` methods
    :func:`Trie.shortest_prefix` and :func:`Trie.longest_prefix`.
    """
    __slots__ = ()

    def __bool__(self) -> _t.Literal[False]:
        return False

    @_t.overload
    def get(self) -> None: ...
    @_t.overload
    def get(self, default: T) -> T: ...
    def get(self, default: T | None=None) -> T | None:
        return default

    is_set = has_subtrie = False

    @property
    def key(self) -> None:
        """None; in the future will raise :class:`KeyError`."""
        _warnings.warn(
            '_NoneStep.key will soon raise KeyError; use `bool(step)` to'
            ' check whether step is real or _NoneStep.',
            DeprecationWarning)

    @property
    def value(self) -> None:
        """None; in the future will raise :class:`KeyError`."""
        _warnings.warn(
            '_NoneStep.value will soon raise KeyError; use'
            ' `step.get(default)` to get value of a step.',
            DeprecationWarning)

    def __getitem__(self, index: int) -> None:
        """Makes object appear like a ``(key, value)`` tuple.

        This is deprecated.  Prefer ``bool(self)`` to detect whether this is
        a :class:`Trie._Step` or ``_NoneStep``; and :func:`Trie._Step.get`
        to get value of the node.

        Args:
            index: Element index to return.

        Returns:
            ``None`` if ``index`` is 0 or 1.

        Raises:
            IndexError: if ``index`` is not 0 or 1.
        """
        if index == 0:
            _warnings.warn(
                'Indexed access to _NoneStep is deprecated; use'
                ' `bool(step)` to check whether step is real or _NoneStep.',
                DeprecationWarning)
            return None
        if index == 1:
            _warnings.warn(
                'Indexed access to _NoneStep is deprecated; use'
                ' `step.get(default)` to get value of a step.',
                DeprecationWarning)
            return None
        raise IndexError('index out of range')

    def __repr__(self) -> str:
        return '(None Step)'

    def __setattr__(self, key: str, value: _t.Any) -> None:
        raise AttributeError('_NoneStep is read only')

_NONE_STEP = _NoneStep()


class _Step(_t.Generic[K, V, S]):
    """Representation of a single step on a path towards particular node.

    *Note:* Reading ``value`` property of this class may raise
    :class:`KeyError` if the node at the step does not have a value.
    Writing the property always succeeds.  :func:`Trie._Step.get` returns
    value or default and always succeeds.

    The class is private because it should not be constructed by external
    code.  Objects of this type are returned by :class:`Trie` methods such
    as :func:`Trie.prefixes` and :func:`Trie.walk_towards`.
    """
    __slots__ = ('_trie', '_path', '_pos', '_node', '__key')

    _trie: 'Trie[K, V, S]'
    _path: _t.Sequence[S]
    _pos: int
    _node: _Node[S, V]
    __key: K

    def __init__(self,
                 trie: 'Trie[K, V, S]',
                 path: _t.Sequence[S],
                 pos: int,
                 node: _Node[S, V]):
        self._trie = trie
        self._path = path
        self._pos = pos
        self._node = node

    def __bool__(self) -> _t.Literal[True]:
        return True

    @property
    def is_set(self) -> bool:
        """Whether the node has value assigned to it."""
        return self._node.value is not _NOVAL

    @property
    def has_subtrie(self) -> bool:
        """Whether the node has any children."""
        return bool(self._node.children)

    @_t.overload
    def get(self) -> V | None: ...
    @_t.overload
    def get(self, default: T) -> V | T: ...
    def get(self, default: T | None=None) -> V | T | None:
        """Returns node's value or the default if value is not assigned."""
        value = self._node.value
        return value if _is_value(value) else default

    def set(self, value: V) -> None:
        """Deprecated.  Use ``step.value = value`` instead."""
        _warnings.warn(
            '_Step.set() is deprecated; use `step.value = expr` instead.',
            DeprecationWarning)
        self._node.value = value

    def setdefault(self, value: V) -> V:
        """Assigns value to the node if one is not set then returns it."""
        if self._node.value is _NOVAL:
            self._node.value = value
        return _t.cast(V, self._node.value)

    def __repr__(self) -> str:
        return '(%r: %r)' % (self.key, self.value)

    @property
    def key(self) -> K:
        """Node’s key."""
        if not hasattr(self, '_Step__key'):
            # pylint:disable=protected-access,attribute-defined-outside-init
            self.__key = self._trie._key_from_path(self._path[:self._pos])
        return self.__key

    @property
    def value(self) -> V:
        """Node's value; on read, raises KeyError if node has no value."""
        if _is_value(value := self._node.value):
            return value
        raise ShortKeyError(self.key)

    @value.setter
    def value(self, value: V) -> None:
        self._node.value = value

    def __getitem__(self, index: int) -> K | V:
        """Makes object appear like a (key, value) tuple.

        This is deprecated.  Prefer :attr:`Trie._Step.key` and
        :attr:`Trie._Step.value` properties or :func:`Trie._Step.get`
        method.

        Args:
            index: Element index to return.

        Returns:
            ``self.key`` if ``index`` is 0 or ``self.value`` if ``index`` is
            1.

        Raises:
            IndexError: if ``index`` is not 0 or 1.
            KeyError: if ``index`` is 1 and the node has no value.
        """
        _warnings.warn(
            'Indexed access to _Step is deprecated; use `step.key` and'
            ' `step.value` instead.',
            DeprecationWarning)
        if index == 0:
            return self.key
        if index == 1:
            return self.value
        raise IndexError('index out of range')


_Trace = list[tuple[S, _Node[S, V]]]


class Trie(_t.Generic[K, V, S], _abc.MutableMapping[K, V]):
    """A trie implementation with dict interface plus some extensions.

    Keys used with the class must be an iterables of hashable objects.  In other
    words, for a given key, ``dict.fromkeys(key)`` must be valid expression.  In
    particular, strings work well as keys, however getting them back (for
    example via :func:`Trie.iterkeys` method), instead of strings, tuples of
    characters are produced.

    Subclasses can modify the way keys are iterated over by overriding
    :func:`Trie._path_from_key` and :func:`Trie._key_from_path`.  For example,
    consider a trie whose keys are Polish postal codes which have format
    ‘xx-yyy’ where ‘xx’ is to be treated as a single number but ‘yyy’ divided by
    digit::

        class PostalTrie(Trie):

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

    :class:`pygtrie.CharTrie` and :class:`pygtrie.StringTrie` classes handle
    cases of iterating over characters of a string and splitting string by
    a separator respectively.
    """

    _root: _Node[S, V]

    def __init__(self,
                 other: _abc.Mapping[K, V] | _t.Iterable[tuple[K, V]]=(),
                 /,
                 **kwargs: V) -> None:
        """Initialises the trie.

        Arguments are interpreted the same way :func:`Trie.update` interprets
        them.
        """
        self._root = _Node()
        self._items_callback = self._ITEMS_CALLBACKS[0]
        self.update(other, **kwargs)

    _ITEMS_CALLBACKS = (lambda x: x.items(), lambda x: x.sorted_items())

    def enable_sorting(self, enable: bool=True) -> None:
        """Enables sorting of child nodes when iterating and traversing.

        Normally, child nodes are not sorted when iterating or traversing over
        the trie (just like dict elements are not sorted).  This method allows
        sorting to be enabled (which was the behaviour prior to pygtrie 2.0
        release).

        For Trie class, enabling sorting of children is identical to simply
        sorting the list of items since Trie returns keys as tuples.  However,
        for other implementations such as StringTrie the two may behave subtly
        different.  For example, sorting items might produce::

            root/foo-bar
            root/foo/baz

        even though foo comes before foo-bar.

        Args:
            enable: Whether to enable sorting of child nodes.
        """
        self._items_callback = self._ITEMS_CALLBACKS[bool(enable)]

    def __getstate__(self) -> dict[str, _t.Any]:
        # encode self._items_callback as self._sorted when pickling
        state = self.__dict__.copy()
        callback = state.pop('_items_callback', None)
        state['_sorted'] = callback is self._ITEMS_CALLBACKS[1]
        return state

    def __setstate__(self, state: dict[str, _t.Any]) -> None:
        # translate self._sorted back to _items_callback when unpickling
        self.__dict__ = state
        self.enable_sorting(state.pop('_sorted'))

    def clear(self) -> None:
        """Removes all the values from the trie."""
        self._root = _Node()

    def update(self,  # type: ignore[override]
               other: _abc.Mapping[K, V] | _t.Iterable[tuple[K, V]] = (),
               /,
               **kwargs: V) -> None:
        """Updates stored values.  Works like :meth:`dict.update`."""
        if isinstance(other, Trie):
            # MutableMapping.update() does `for key in other: self[key] =
            # other[key]` which performs key lookup twice.  If we’re dealing
            # with a Trie, that’s quite expensive so convert `other` to an
            # iterator over items of the trie.
            other = other.items()
        super().update(other, **kwargs)

    def merge(self, other: 'Trie[K, V, S]', overwrite: bool=False) -> None:
        """Moves nodes from other trie into this one.

        The merging happens at trie structure level and as such is different
        than iterating over items of one trie and setting them in the other
        trie.

        The merging may happen between different types of tries resulting in
        different (key, value) pairs in the destination trie compared to the
        source.  For example, merging two :class:`pygtrie.StringTrie` objects
        each using different separators will work as if the other trie had
        separator of this trie.  Similarly, a :class:`pygtrie.CharTrie` may be
        merged into a :class:`pygtrie.StringTrie` but when keys are read those
        will be joined by the separator.  For example:

            >>> import pygtrie
            >>> st = pygtrie.StringTrie(separator='.')
            >>> st.merge(pygtrie.StringTrie({'foo/bar': 42}))
            >>> list(st.items())
            [('foo.bar', 42)]
            >>> st.merge(pygtrie.CharTrie({'baz': 24}))
            >>> sorted(st.items())
            [('b.a.z', 24), ('foo.bar', 42)]

        Not all tries can be merged into other tries.  For example,
        a :class:`pygtrie.StringTrie` may not be merged into
        a :class:`pygtrie.CharTrie` because the latter imposes a requirement for
        each component in the key to be exactly one character while in the
        former components may be arbitrary length.

        Note that the other trie is cleared and any references or iterators over
        it are invalidated.  To preserve other’s value it needs to be copied
        first.

        Args:
            other: Other trie to move nodes from.
            overwrite: Whether to overwrite existing values in this trie.
        """
        if isinstance(self, type(other)):
            self._merge_impl(self, other, overwrite=overwrite)
        else:
            other._merge_impl(self, other, overwrite=overwrite) # pylint: disable=protected-access
        other.clear()

    @classmethod
    def _merge_impl(cls, dst: _t.Self, src: _t.Self, overwrite: bool) -> None:
        # pylint: disable=protected-access
        dst._root.merge(src._root, overwrite=overwrite)

    def __copy(self, make_copy: _MakeCopy=lambda x: x) -> _t.Self:
        """Returns a shallow copy of the object.

        Args:
            make_copy: Function copying values.  If not given, values won’t be
                copied.
        """
        cpy = self.__class__()
        cpy.__dict__ = self.__dict__.copy()
        cpy._root = self._root.copy(make_copy) # pylint: disable=protected-access
        return cpy

    def copy(self) -> _t.Self:
        """Returns a shallow copy of the object."""
        return self.__copy()

    def __copy__(self) -> _t.Self:
        return self.__copy()

    def __deepcopy__(self, memo: dict[int, _t.Any]) -> _t.Self:
        def _deep_copy(value: T) -> T:
            return _copy.deepcopy(value, memo)
        return self.__copy(_deep_copy)

    @_t.overload
    @classmethod
    def fromkeys(cls, keys: _t.Iterable[K]) -> 'Trie[K, V, S]': ...
    @_t.overload
    @classmethod
    def fromkeys(cls, keys: _t.Iterable[K], value: V) -> 'Trie[K, V, S]': ...
    @classmethod
    def fromkeys(cls,
                 keys: _t.Iterable[K],
                 value: V | None=None) -> 'Trie[K, V, S]':
        """Creates a new trie with given keys set.

        This is equivalent to calling the constructor with a ``(key, value) for
        key in keys`` generator.

        Args:
            keys: An iterable of keys that should be set in the new trie.
            value: Value to associate with given keys.  The value is not copied;
                all keys reference the same object.

        Returns:
            A new trie where each key from ``keys`` is set to the given value.
        """
        trie = cls()
        for key in keys:
            trie[key] = _t.cast(V, value)
        return trie

    def _get_node(self, key: K | _Sentinel) -> tuple[_Node[S, V], _Trace[S, V]]:
        """Returns node for given key.  Creates it if requested.

        Args:
            key: A key to look for.

        Returns:
            ``(node, trace)`` tuple where ``node`` is the node for given key and
            ``trace`` is a list specifying path to reach the node including all
            the encountered nodes.  Each element of trace is a ``(step, node)``
            tuple where ``step`` is a step from parent node to given node and
            ``node`` is node on the path.  The first element of the path is
            always ``(None, self._root)``.

        Raises:
            KeyError: If there is no node for the key.
        """
        node = self._root
        trace: list[tuple[S | None, _Node[S, V]]] = [(None, node)]
        for step in self.__path_from_key(key):
            # pylint thinks node.children is always _NoChildren and thus that
            # we’re assigning None here; pylint: disable=assignment-from-none
            n = node.children.get(step)
            if n is None:
                raise KeyError(key)
            node = n
            trace.append((step, node))
        # The first element of trace has a `None` step, but we’re lying about
        # the type to make the rest of the code less noisy.  In practice, the
        # first step is never accessed and the first element is only used to
        # keep the root node.
        return node, _t.cast(_Trace[S, V], trace)

    def _set_node(self,
                  key: K,
                  value: V,
                  only_if_missing: bool=False) -> _Node[S, V]:
        """Sets value for a given key.

        Args:
            key: Key to set value of.
            value: Value to set to.
            only_if_missing: If true, value won't be changed if the key is
                already associated with a value.

        Returns:
            The node.
        """
        node = self._root
        for step in self.__path_from_key(key):
            node = node.children.require(node, step)
        if node.value is _NOVAL or not only_if_missing:
            node.value = value
        return node

    def _set_node_if_no_prefix(self, key: K) -> None:
        """Sets given key to True but only if none of its prefixes are present.

        If value is set, removes all ancestors of the node.

        This is a method for exclusive use by PrefixSet.

        Args:
            key: Key to set value of.
        """
        steps = iter(self.__path_from_key(key))
        node = self._root
        try:
            while node.value is _NOVAL:
                node = node.children.require(node, next(steps))
        except StopIteration:
            # This method is only used when V is bool.
            node.value = _t.cast(V, True)
            node.children = _NoChildren()

    def __iter__(self) -> _t.Iterator[K]:
        return self.iterkeys()

    # pylint: disable=arguments-differ

    def iteritems(self,
                  prefix: K | _Sentinel=_SENTINEL,
                  shallow: bool=False) -> _t.Iterator[tuple[K, V]]:
        """Yields all nodes with associated values with given prefix.

        Only nodes with values are output.  For example::

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo'] = 'Foo'
            >>> t['foo/bar/baz'] = 'Baz'
            >>> t['qux'] = 'Qux'
            >>> sorted(t.items())
            [('foo', 'Foo'), ('foo/bar/baz', 'Baz'), ('qux', 'Qux')]

        Items are generated in topological order (i.e. parents before child
        nodes) but the order of siblings is unspecified.  At an expense of
        efficiency, :func:`Trie.enable_sorting` method can turn deterministic
        ordering of siblings.

        With ``prefix`` argument, only items with specified prefix are generated
        (i.e. only given subtrie is traversed) as demonstrated by::

            >>> t.items(prefix='foo')
            [('foo', 'Foo'), ('foo/bar/baz', 'Baz')]

        With ``shallow`` argument, if a node has value associated with it, it's
        children are not traversed even if they exist which can be seen in::

            >>> sorted(t.items(shallow=True))
            [('foo', 'Foo'), ('qux', 'Qux')]

        Args:
            prefix: If given, prefix to limit iteration to.
            shallow: Perform a shallow traversal, i.e. do not yield items if
                their prefix has been yielded.

        Yields:
            ``(key, value)`` tuples.

        Raises:
            KeyError: If ``prefix`` does not match any node.
        """
        node, _ = self._get_node(prefix)
        for path, value in node.iterate(list(self.__path_from_key(prefix)),
                                        shallow, self._items_callback):
            yield (self._key_from_path(path), value)

    def iterkeys(self,
                 prefix: K | _Sentinel=_SENTINEL,
                 shallow: bool=False) -> _t.Iterator[K]:
        """Yields all keys having associated values with given prefix.

        This is equivalent to taking first element of tuples generated by
        :func:`Trie.iteritems` which see for more detailed documentation.

        Args:
            prefix: If given, prefix to limit iteration to.
            shallow: Perform a shallow traversal, i.e. do not yield keys if
                their prefix has been yielded.

        Yields:
            All the keys (with given prefix) with associated values in the trie.

        Raises:
            KeyError: If ``prefix`` does not match any node.
        """
        for key, _ in self.iteritems(prefix=prefix, shallow=shallow):
            yield key

    def itervalues(self,
                   prefix: K | _Sentinel=_SENTINEL,
                   shallow: bool=False) -> _t.Iterator[V]:
        """Yields all values associated with keys with given prefix.

        This is equivalent to taking second element of tuples generated by
        :func:`Trie.iteritems` which see for more detailed documentation.

        Args:
            prefix: If given, prefix to limit iteration to.
            shallow: Perform a shallow traversal, i.e. do not yield values if
                their prefix has been yielded.

        Yields:
            All the values associated with keys (with given prefix) in the trie.

        Raises:
            KeyError: If ``prefix`` does not match any node.
        """
        node, _ = self._get_node(prefix)
        for _, value in node.iterate(list(self.__path_from_key(prefix)),
                                     shallow, self._items_callback):
            yield value

    def items(self,  # type: ignore[override]
              prefix: K | _Sentinel=_SENTINEL,
              shallow: bool=False) -> list[tuple[K, V]]:
        """Returns a list of ``(key, value)`` pairs in given subtrie.

        This is equivalent to constructing a list from generator returned by
        :func:`Trie.iteritems` which see for more detailed documentation.
        """
        return list(self.iteritems(prefix=prefix, shallow=shallow))

    def keys(self,  # type: ignore[override]
              prefix: K | _Sentinel=_SENTINEL,
              shallow: bool=False) -> list[K]:
        """Returns a list of all the keys, with given prefix, in the trie.

        This is equivalent to constructing a list from generator returned by
        :func:`Trie.iterkeys` which see for more detailed documentation.
        """
        return list(self.iterkeys(prefix=prefix, shallow=shallow))

    def values(self,  # type: ignore[override]
              prefix: K | _Sentinel=_SENTINEL,
              shallow: bool=False) -> list[V]:
        """Returns a list of values in given subtrie.

        This is equivalent to constructing a list from generator returned by
        :func:`Trie.itervalues` which see for more detailed documentation.
        """
        return list(self.itervalues(prefix=prefix, shallow=shallow))

    def __len__(self) -> int:
        """Returns the number of values in the trie.

        This method is expensive to run as it iterates over the whole trie.
        """
        return sum(1 for _ in self.itervalues())

    def __bool__(self) -> bool:
        return self._root.value is not _NOVAL or bool(self._root.children)

    __hash__ = None  # type: ignore[assignment]

    HAS_VALUE = 1
    HAS_SUBTRIE = 2

    def has_node(self, key: K) -> int:
        """Returns whether given node is in the trie.

        Return value is a bitwise or of ``HAS_VALUE`` and ``HAS_SUBTRIE``
        constants indicating node has a value associated with it and that it is
        a prefix of another existing key respectively.  Both of those are
        independent of each other and all of the four combinations are possible.
        For example::

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo/bar'] = 'Bar'
            >>> t['foo/bar/baz'] = 'Baz'
            >>> t.has_node('qux') == 0
            True
            >>> t.has_node('foo/bar/baz') == pygtrie.Trie.HAS_VALUE
            True
            >>> t.has_node('foo') == pygtrie.Trie.HAS_SUBTRIE
            True
            >>> t.has_node('foo/bar') == (pygtrie.Trie.HAS_VALUE |
            ...                           pygtrie.Trie.HAS_SUBTRIE)
            True

        There are two higher level methods built on top of this one which give
        easier interface for the information. :func:`Trie.has_key` returns
        whether node has a value associated with it and :func:`Trie.has_subtrie`
        checks whether node is a prefix.  Continuing previous example::

            >>> t.has_key('qux'), t.has_subtrie('qux')
            (False, False)
            >>> t.has_key('foo/bar/baz'), t.has_subtrie('foo/bar/baz')
            (True, False)
            >>> t.has_key('foo'), t.has_subtrie('foo')
            (False, True)
            >>> t.has_key('foo/bar'), t.has_subtrie('foo/bar')
            (True, True)

        Args:
            key: A key to look for.

        Returns:
            Non-zero if node exists and if it does a bit-field denoting whether
            it has a value associated with it and whether it has a subtrie.
        """
        try:
            node, _ = self._get_node(key)
        except KeyError:
            return 0
        return ((self.HAS_VALUE * (node.value is not _NOVAL)) |
                (self.HAS_SUBTRIE * bool(node.children)))

    def has_key(self, key: K) -> bool:
        """Indicates whether given key has value associated with it.

        See :func:`Trie.has_node` for more detailed documentation.
        """
        return bool(self.has_node(key) & self.HAS_VALUE)

    def has_subtrie(self, key: K) -> bool:
        """Returns whether given key is a prefix of another key in the trie.

        See :func:`Trie.has_node` for more detailed documentation.
        """
        return bool(self.has_node(key) & self.HAS_SUBTRIE)

    @staticmethod
    def _slice_maybe(key_or_slice: K | slice) -> tuple[K, bool]:
        """Checks whether argument is a slice or a plain key.

        Args:
            key_or_slice: A key or a slice to test.

        Returns:
            ``(key, is_slice)`` tuple.  ``is_slice`` indicates whether
            ``key_or_slice`` is a slice and ``key`` is either ``key_or_slice``
            itself (if it's not a slice) or slice's start position.

        Raises:
            TypeError: If ``key_or_slice`` is a slice whose stop or step are not
                ``None`` In other words, only ``[key:]`` slices are valid.
        """
        if isinstance(key_or_slice, slice):
            if key_or_slice.stop is not None or key_or_slice.step is not None:
                raise TypeError(key_or_slice)
            return _t.cast(K, key_or_slice.start), True
        return key_or_slice, False

    @_t.overload
    def __getitem__(self, key_or_slice: K) -> V: ...
    @_t.overload
    def __getitem__(self, key_or_slice: slice) -> _t.Iterator[V]: ...
    def __getitem__(self, key_or_slice: K | slice) -> V | _t.Iterator[V]:
        """Returns value associated with given key or raises :class:`KeyError`.

        When argument is a single key, value for that key is returned (or
        :class:`KeyError` exception is thrown if the node does not exist or has
        no value associated with it).

        When argument is a slice, it must be one with only `start` set in which
        case the access is identical to :func:`Trie.itervalues` invocation with
        prefix argument.

        Example:

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo/bar'] = 'Bar'
            >>> t['foo/baz'] = 'Baz'
            >>> t['qux'] = 'Qux'
            >>> t['foo/bar']
            'Bar'
            >>> sorted(t['foo':])
            ['Bar', 'Baz']
            >>> t['foo']  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
                ...
            ShortKeyError: 'foo'

        Args:
            key_or_slice: A key or a slice to look for.

        Returns:
            If a single key is passed, a value associated with given key.  If
            a slice is passed, a generator of values in specified subtrie.

        Raises:
            ShortKeyError: If the key has no value associated with it but is
                a prefix of some key with a value.  Note that
                :class:`ShortKeyError` is subclass of :class:`KeyError`.
            KeyError: If key has no value associated with it nor is a prefix of
                an existing key.
            TypeError: If ``key_or_slice`` is a slice but it's stop or step are
                not ``None``.
        """
        key, is_slice = self._slice_maybe(key_or_slice)
        if is_slice:
            return self.itervalues(key)
        node, _ = self._get_node(key)
        if _is_value(value := node.value):
            return value
        raise ShortKeyError(key)

    def __setitem__(self, key_or_slice: K | slice, value: V) -> None:
        """Sets value associated with given key.

        If `key_or_slice` is a key, simply associate it with given value.  If it
        is a slice (which must have `start` set only), it in addition clears any
        subtrie that might have been attached to particular key.  For example::

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo/bar'] = 'Bar'
            >>> t['foo/baz'] = 'Baz'
            >>> sorted(t.keys())
            ['foo/bar', 'foo/baz']
            >>> t['foo':] = 'Foo'
            >>> t.keys()
            ['foo']

        Args:
            key_or_slice: A key to look for or a slice.  If it is a slice, the
                whole subtrie (if present) will be replaced by a single node
                with given value set.
            value: Value to set.

        Raises:
            TypeError: If key is a slice whose stop or step are not None.
        """
        key, is_slice = self._slice_maybe(key_or_slice)
        node = self._set_node(key, value)
        if is_slice:
            node.children = _NoChildren()

    def setdefault(self,
                   key: K,
                   default: V=None) -> V:  # type: ignore[assignment]
        """Sets value of a given node if not set already.  Also returns it.

        In contrast to :func:`Trie.__setitem__`, this method does not accept
        slice as a key.

        **Typing:** Calling the method with one argument is only valid if values
        stored in the trie, i.e. the ``V`` generic argument, can be assigned
        value ``None``.
        """
        node = self._set_node(key, default, only_if_missing=True)
        return _t.cast(V, node.value)

    @staticmethod
    def _pop_value(trace: _Trace[S, V]) -> V | _NoValue:
        """Removes value from given node and removes any empty nodes.

        Args:
            trace: Trace to the node to cleanup as returned by
                :func:`Trie._get_node`.  The last element of the trace denotes
                the node to get value of.

        Returns:
            Value which was held in the node at the end of specified trace.
            This may be ``_NOVAL`` if the node didn’t have a value in the first
            place.
        """
        i = len(trace) - 1  # len(path) >= 1 since root is always there
        step, node = trace[i]
        value, node.value = node.value, _NOVAL
        while i and node.value is _NOVAL and not node.children:
            i -= 1
            parent_step, parent = trace[i]
            parent.children.delete(parent, step)
            step, node = parent_step, parent
        return value

    def pop(self, key: K, default: T | _Sentinel=_SENTINEL) -> V | T:
        """Deletes value associated with given key and returns it.

        Args:
            key: A key to look for.
            default: If specified, value that will be returned if given key has
                no value associated with it.  If not specified, method will
                throw :class:`KeyError` in such cases.

        Returns:
            Removed value, if key had value associated with it, or ``default``
            (if given).

        Raises:
            ShortKeyError: If ``default`` has not been specified and the key has
                no value associated with it but is a prefix of some key with
                a value.  Note that :class:`ShortKeyError` is subclass of
                :class:`KeyError`.
            KeyError: If default has not been specified and key has no value
                associated with it nor is a prefix of an existing key.
        """
        try:
            _, trace = self._get_node(key)
            value = self._pop_value(trace)
            if _is_value(value):
                return value
            raise ShortKeyError()
        except KeyError:
            if _is_not_sentinel(default):
                return default
            raise

    def popitem(self) -> tuple[K, V]:
        """Deletes an arbitrary value from the trie and returns it.

        There is no guarantee as to which item is deleted and returned.  Neither
        in respect to its lexicographical nor topological order.

        Returns:
            ``(key, value)`` tuple indicating deleted key.

        Raises:
            KeyError: If the trie is empty.
        """
        if not self:
            raise KeyError()
        node = self._root
        # The first element of the trace is never accessed.  We lie about it’s
        # type to simplify the code and avoid redundant casts and checks.
        trace: _Trace[S, V] = [(_t.cast(S, None), node)]
        while not _is_value(value := node.value):
            # If node has no value, it must have children.
            step, node = node.children.pick()
            trace.append((step, node))
        key = self._key_from_path((step for step, _ in trace[1:]))
        self._pop_value(trace)
        return key, value

    def __delitem__(self, key_or_slice: K | slice) -> None:
        """Deletes value associated with given key or raises KeyError.

        If argument is a key, value associated with it is deleted.  If the key
        is also a prefix, its descendents are not affected.  On the other hand,
        if the argument is a slice (in which case it must have only start set),
        the whole subtrie is removed.  For example::

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo'] = 'Foo'
            >>> t['foo/bar'] = 'Bar'
            >>> t['foo/bar/baz'] = 'Baz'
            >>> del t['foo/bar']
            >>> t.keys()
            ['foo', 'foo/bar/baz']
            >>> del t['foo':]
            >>> t.keys()
            []

        Args:
            key_or_slice: A key to look for or a slice.  If key is a slice, the
                    whole subtrie will be removed.

        Raises:
            ShortKeyError: If the key has no value associated with it but is
                a prefix of some key with a value.  This is not thrown if
                key_or_slice is a slice -- in such cases, the whole subtrie is
                removed.  Note that :class:`ShortKeyError` is subclass of
                :class:`KeyError`.
            KeyError: If key has no value associated with it nor is a prefix of
                an existing key.
            TypeError: If key is a slice whose stop or step are not ``None``.
        """
        key, is_slice = self._slice_maybe(key_or_slice)
        node, trace = self._get_node(key)
        if is_slice:
            node.children = _NoChildren()
        elif node.value is _NOVAL:
            raise ShortKeyError(key)
        self._pop_value(trace)


    _Step: _t.TypeAlias = _Step
    _NoneStep: _t.TypeAlias = _NoneStep

    def walk_towards(self, key: K) -> _t.Iterator[_Step[K, V, S]]:
        """Yields nodes on the path to given node.

        Args:
            key: Key of the node to look for.

        Yields:
            :class:`pygtrie._Step` objects which can be used to extract or set
            node's value as well as get node's key.

            When representing nodes with assigned values, the objects can be
            treated as ``(k, value)`` pairs denoting keys with associated values
            encountered on the way towards the specified key.  This is
            deprecated, prefer using ``key`` and ``value`` properties or ``get``
            method of the object.

        Raises:
            KeyError: If node with given key does not exist.  It's all right if
                they value is not assigned to the node provided it has a child
                node.  Because the method is a generator, the exception is
                raised only once a missing node is encountered.
        """
        node = self._root
        path = self.__path_from_key(key)
        pos = 0
        while True:
            yield _Step(self, path, pos, node)
            if pos == len(path):
                break
            # pylint thinks node.children is always _NoChildren and thus that
            # we’re assigning None here; pylint: disable=assignment-from-none
            n = node.children.get(path[pos])
            if n is None:
                raise KeyError(key)
            node = n
            pos += 1

    def prefixes(self, key: K) -> _t.Iterator[_Step[K, V, S]]:
        """Walks towards the node specified by key and yields all found items.

        Example:

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo'] = 'Foo'
            >>> t['foo/bar/baz'] = 'Baz'
            >>> list(t.prefixes('foo/bar/baz/qux'))
            [('foo': 'Foo'), ('foo/bar/baz': 'Baz')]
            >>> list(t.prefixes('does/not/exist'))
            []

        Args:
            key: Key to look for.

        Yields:
            :class:`pygtrie._Step` objects which can be used to extract or set
            node's value and get its key.

            The objects can be treated as ``(k, value)`` pairs denoting keys
            with associated values encountered on the way towards the specified
            key.  This is deprecated, prefer using ``key`` and ``value``
            properties of the object.
        """
        try:
            for step in self.walk_towards(key):
                if step.is_set:
                    yield step
        except KeyError:
            pass

    def shortest_prefix(self, key: K) -> _NoneStep | _Step[K, V, S]:
        """Finds the shortest prefix of a key with a value.

        This is roughly equivalent to taking the first object yielded by
        :func:`Trie.prefixes` with additional handling for situations when no
        prefixes are found.

        Example:

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo'] = 'Foo'
            >>> t['foo/bar/baz'] = 'Baz'
            >>> t.shortest_prefix('foo/bar/baz/qux')
            ('foo': 'Foo')
            >>> t.shortest_prefix('foo/bar/baz/qux').key
            'foo'
            >>> t.shortest_prefix('foo/bar/baz/qux').value
            'Foo'
            >>> t.shortest_prefix('does/not/exist')
            (None Step)
            >>> bool(t.shortest_prefix('does/not/exist'))
            False

        Args:
            key: Key to look for.

        Returns:
            :class:`pygtrie._Step` object (which can be used to extract or set
            node's value and get its key), or a :class:`pygtrie._NoneStep`
            object (which is falsy value simulating a _Step with ``None`` key
            and value) if no prefix is found.

            The object can be treated as ``(key, value)`` pair denoting key with
            associated value of the prefix.  This is deprecated, prefer using
            ``key`` and ``value`` properties of the object.
        """
        return next(self.prefixes(key), _NONE_STEP)

    def longest_prefix(self, key: K) -> _NoneStep | _Step[K, V, S]:
        """Finds the longest prefix of a key with a value.

        This is roughly equivalent to taking the last object yielded by
        :func:`Trie.prefixes` with additional handling for situations when no
        prefixes are found.

        Example:

            >>> import pygtrie
            >>> t = pygtrie.StringTrie()
            >>> t['foo'] = 'Foo'
            >>> t['foo/bar/baz'] = 'Baz'
            >>> t.longest_prefix('foo/bar/baz/qux')
            ('foo/bar/baz': 'Baz')
            >>> t.longest_prefix('foo/bar/baz/qux').key
            'foo/bar/baz'
            >>> t.longest_prefix('foo/bar/baz/qux').value
            'Baz'
            >>> t.longest_prefix('does/not/exist')
            (None Step)
            >>> bool(t.longest_prefix('does/not/exist'))
            False

        Args:
            key: Key to look for.

        Returns:
            :class:`pygtrie._Step` object (which can be used to extract or
            set node's value as well as get node's key), or
            a :class:`pygtrie._NoneStep` object (which is falsy value simulating
            a _Step with ``None`` key and value) if no prefix is found.

            The object can be treated as ``(key, value)`` pair denoting key with
            associated value of the prefix.  This is deprecated, prefer using
            ``key`` and ``value`` properties of the object.
        """
        ret: _NoneStep | _Step[K, V, S] = _NONE_STEP
        for ret in self.prefixes(key):
            pass
        return ret

    def strictly_equals(self, other: 'Trie[K, V, S]') -> bool:
        """Checks whether tries are equal with the same structure.

        This is stricter comparison than the one performed by equality operator.
        It not only requires keys and values to be equal but also the two tries
        to be of the same type and have the same structure.

        For example, two :class:`pygtrie.StringTrie` objects compare equal, they
        need to have the same structure as well as the same separator as seen
        below:

            >>> import pygtrie
            >>> t0 = StringTrie({'foo/bar.baz': 42}, separator='/')
            >>> t1 = StringTrie({'foo/bar.baz': 42}, separator='.')
            >>> t0 == t1
            True
            >>> t0.strictly_equals(t1)
            False

        Args:
            other: Other trie to compare to.

        Returns:
            Whether the two tries are the same type and have the same structure.
        """
        if self is other:
            return True
        if type(self) != type(other):
            return False
        result = self._eq_impl(other)
        if result is NotImplemented:
            return False
        else:
            return result

    def __eq__(self, other: object) -> bool:
        """Compares this trie’s mapping with another mapping.

        Note that this method doesn’t take trie’s structure into consideration.
        What matters is whether keys and values in both mappings are the same.
        This may lead to unexpected results, for example:

            >>> import pygtrie
            >>> t0 = StringTrie({'foo/bar': 42}, separator='/')
            >>> t1 = StringTrie({'foo.bar': 42}, separator='.')
            >>> t0 == t1
            False

            >>> t0 = StringTrie({'foo/bar.baz': 42}, separator='/')
            >>> t1 = StringTrie({'foo/bar.baz': 42}, separator='.')
            >>> t0 == t1
            True

            >>> t0 = Trie({'foo': 42})
            >>> t1 = CharTrie({'foo': 42})
            >>> t0 == t1
            False

        This behaviour is required to maintain consistency with Mapping
        interface and its __eq__ method.  For example, this implementation
        maintains transitivity of the comparison:

            >>> t0 = StringTrie({'foo/bar.baz': 42}, separator='/')
            >>> d = {'foo/bar.baz': 42}
            >>> t1 = StringTrie({'foo/bar.baz': 42}, separator='.')
            >>> t0 == d
            True
            >>> d == t1
            True
            >>> t0 == t1
            True

            >>> t0 = Trie({'foo': 42})
            >>> d = {'foo': 42}
            >>> t1 = CharTrie({'foo': 42})
            >>> t0 == d
            False
            >>> d == t1
            True
            >>> t0 == t1
            False

        Args:
            other: Other object to compare to.

        Returns:
            ``NotImplemented`` if this method does not know how to perform the
            comparison or a ``bool`` denoting whether the two objects are equal
            or not.
        """
        if self is other:
            return True
        if type(other) == type(self):
            result = self._eq_impl(other)
            if result is not NotImplemented:
                return result
        return super().__eq__(other)

    def _eq_impl(self, other: _t.Self) -> bool | _types.NotImplementedType:
        return self._root.equals(other._root) # pylint: disable=protected-access

    def __ne__(self, other: object) -> bool:
        return not self == other

    def _str_items(self, fmt: str='%s: %s') -> str:
        return ', '.join(fmt % item for item in self.iteritems())

    def __str__(self) -> str:
        return '%s(%s)' % (type(self).__name__, self._str_items())

    def __repr__(self) -> str:
        return '%s([%s])' % (type(self).__name__, self._str_items('(%r, %r)'))

    def __path_from_key(self, key: K | _Sentinel) -> _t.Sequence[S]:
        """Converts a user visible key object to internal path representation.

        Args:
            key: User supplied key or ``_SENTINEL``.

        Returns:
            An empty tuple if ``key`` was ``_SENTINEL``, otherwise whatever
            :func:`Trie._path_from_key` returns.

        Raises:
            TypeError: If ``key`` is of invalid type.
        """
        return self._path_from_key(key) if _is_not_sentinel(key) else ()

    def _path_from_key(self, key: K) -> _t.Sequence[S]:
        """Converts a user visible key object to internal path representation.

        The default implementation simply returns key.

        Args:
            key: User supplied key.

        Returns:
            A path, which is an iterable of steps.  Each step must be hashable.

        Raises:
            TypeError: If key is of invalid type.
        """
        return _t.cast(_t.Sequence[S], key)

    def _key_from_path(self, path: _t.Iterable[S]) -> K:
        """Converts an internal path into a user visible key object.

        The default implementation creates a tuple from the path.

        Args:
            path: Internal path representation.
        Returns:
            A user visible key object.
        """
        return _t.cast(K, tuple(path))

    def traverse(
            self,
            node_factory: _t.Callable[..., T],
            prefix: K | _Sentinel=_SENTINEL) -> T:
        """Traverses the tree using node_factory object.

        node_factory is a callable which accepts (path_conv, path, children,
        value=...) arguments, where path_conv is a lambda converting path
        representation to key, path is the path to this node, children is an
        iterable of children nodes constructed by node_factory, optional value
        is the value associated with the path.

        node_factory's children argument is a lazy iterable which has a few
        consequences:

        * To traverse into node's children, the object must be iterated over.
          This can by accomplished by a simple ``children = list(children)``
          statement.
        * Ignoring the argument allows node_factory to stop the traversal from
          going into the children of the node.  In other words, whole subtries
          can be removed from traversal if node_factory chooses so.
        * If children is stored as is (i.e. as a iterator) when it is iterated
          over later on it may see an inconsistent state of the trie if it has
          changed between invocation of this method and the iteration.

        However, to allow constant-time determination whether the node has
        children or not, the iterator implements bool conversion such that
        ``has_children = bool(children)`` will tell whether node has children
        without iterating over them.  (Note that ``bool(children)`` will
        continue returning ``True`` even if the iterator has been iterated
        over).

        :func:`Trie.traverse` has two advantages over :func:`Trie.iteritems` and
        similar methods:

        1. it allows subtries to be skipped completely when going through the
           list of nodes based on the property of the parent node; and

        2. it represents structure of the trie directly making it easy to
           convert structure into a different representation.

        For example, the below snippet prints all files in current directory
        counting how many HTML files were found but ignores hidden files and
        directories (i.e. those whose names start with a dot)::

            import os
            import pygtrie

            t = pygtrie.StringTrie(separator=os.sep)

            # Construct a trie with all files in current directory and all
            # of its sub-directories.  Files get set a True value.
            # Directories are represented implicitly by being prefixes of
            # files.
            for root, _, files in os.walk('.'):
                for name in files: t[os.path.join(root, name)] = True

            def traverse_callback(path_conv, path, children, is_file=False):
                if path and path[-1] != '.' and path[-1][0] == '.':
                    # Ignore hidden directory (but accept root node and '.')
                    return 0
                elif is_file:
                    print path_conv(path)
                    return int(path[-1].endswith('.html'))
                else:
                    # Otherwise, it's a directory.  Traverse into children.
                    return sum(children)

            print t.traverse(traverse_callback)

        As documented, ignoring the children argument causes subtrie to be
        omitted and not walked into.

        In the next example, the trie is converted to a tree representation
        where child nodes include a pointer to their parent.  As before, hidden
        files and directories are ignored::

            import os
            import pygtrie

            t = pygtrie.StringTrie(separator=os.sep)
            for root, _, files in os.walk('.'):
                for name in files: t[os.path.join(root, name)] = True

            class File:
                def __init__(self, name):
                    self.name = name
                    self.parent = None

            class Directory(File):
                def __init__(self, name, children):
                    super().__init__(name)
                    self._children = children
                    for child in children:
                        child.parent = self

            def traverse_callback(path_conv, path, children, is_file=False):
                if not path or path[-1] == '.' or path[-1][0] != '.':
                    if is_file:
                        return File(path[-1])
                    children = filter(None, children)
                    return Directory(path[-1] if path else '', children)

            root = t.traverse(traverse_callback)

        Note: Unlike iterators, when used on a deep trie, traverse method is
        prone to rising a RuntimeError exception when Python's maximum recursion
        depth is reached.  This can be addressed by not iterating over children
        inside of the node_factory.  For example, the below code converts a trie
        into an undirected graph using adjacency list representation::

            def undirected_graph_from_trie(t):
                '''Converts trie into a graph and returns its nodes.'''

                Node = collections.namedtuple('Node', 'path neighbours')

                class Builder:
                    def __init__(self, path_conv, path, children, _=None):
                        self.node = Node(path_conv(path), [])
                        self.children = children
                        self.parent = None

                    def build(self, queue):
                        for builder in self.children:
                            builder.parent = self.node
                            queue.append(builder)
                        if self.parent:
                            self.parent.neighbours.append(self.node)
                            self.node.neighbours.append(self.parent)
                        return self.node

                nodes = [t.traverse(Builder)]
                i = 0
                while i < len(nodes):
                    nodes[i] = nodes[i].build(nodes)
                    i += 1
                return nodes

        Args:
            node_factory: Makes opaque objects from the keys and values of the
                trie.
            prefix: Prefix for node to start traversal, by default starts at
                root.

        Returns:
            Node object constructed by node_factory corresponding to the root
            node.
        """
        node, _ = self._get_node(prefix)
        return node.traverse(node_factory, self._key_from_path,
                             list(self.__path_from_key(prefix)),
                             self._items_callback)

    traverse.uses_bool_convertible_children = True  # type: ignore[attr-defined]


class CharTrie(Trie[str, V, str]):
    """A variant of a :class:`pygtrie.Trie` which accepts strings as keys.

    The only difference between :class:`pygtrie.CharTrie` and
    :class:`pygtrie.Trie` is that when :class:`pygtrie.CharTrie` returns keys
    back to the client (for instance when :func:`Trie.keys` method is called),
    those keys are returned as strings.

    Common example where this class can be used is a dictionary of words in
    a natural language.  For example::

        >>> import pygtrie
        >>> t = pygtrie.CharTrie()
        >>> t['wombat'] = True
        >>> t['woman'] = True
        >>> t['man'] = True
        >>> t['manhole'] = True
        >>> t.has_subtrie('wo')
        True
        >>> t.has_key('man')
        True
        >>> t.has_subtrie('man')
        True
        >>> t.has_subtrie('manhole')
        False
    """

    def _key_from_path(self, path: _t.Iterable[str]) -> str:
        return ''.join(path)


class StringTrie(_t.Generic[V], Trie[str, V, str]):
    """:class:`pygtrie.Trie` variant accepting strings with a separator as keys.

    The trie accepts strings as keys which are split into components using
    a separator specified during initialisation (forward slash, i.e. ``/``, by
    default).

    Common example where this class can be used is when keys are paths.  For
    example, it could map from a path to a request handler::

        import pygtrie

        def handle_root(): pass
        def handle_admin(): pass
        def handle_admin_images(): pass

        handlers = pygtrie.StringTrie()
        handlers[''] = handle_root
        handlers['/admin'] = handle_admin
        handlers['/admin/images'] = handle_admin_images

        request_path = '/admin/images/foo'

        handler = handlers.longest_prefix(request_path)
    """

    def __init__(self,
                 other: _abc.Mapping[str, V] | _t.Iterable[tuple[str, V]]=(),
                 /,
                 separator: str='/',
                 **kwargs: V) -> None:
        """Initialises the trie.

        Except for a ``separator`` named argument, all other arguments are
        interpreted the same way :func:`Trie.update` interprets them.

        Args:
            other: Passed to super class initialiser.
            separator: A separator to use when splitting keys into paths used by
                the trie.  "/" is used if this argument is not specified.  This
                named argument is not specified on the function's prototype
                because of Python's limitations.
            **kwargs: Passed to super class initialiser.

        Raises:
            TypeError: If ``separator`` is not a string.
            ValueError: If ``separator`` is empty.
        """
        if not isinstance(separator, str):
            raise TypeError('separator must be a string')
        if not separator:
            raise ValueError('separator cannot be empty')
        self._separator = separator
        super().__init__(other, **kwargs)

    @_t.overload
    @classmethod
    def fromkeys(cls,
                 keys: _t.Iterable[str],
                 *,
                 separator: str='/') -> 'StringTrie[_t.Any]': ...
    @_t.overload
    @classmethod
    def fromkeys(cls,  # pylint: disable=arguments-differ
                 keys: _t.Iterable[str],
                 value: V,
                 separator: str='/') -> 'StringTrie[V]': ...
    @classmethod
    def fromkeys(cls,
                 keys: _t.Iterable[str],
                 value: V | None=None,
                 separator: str='/') -> 'StringTrie[V]':
        trie = cls(separator=separator)
        for key in keys:
            trie[key] = _t.cast(V, value)
        return trie

    @classmethod
    def _merge_impl(cls, dst: _t.Self, src: _t.Self, overwrite: bool) -> None:
        if not isinstance(dst, StringTrie):
            raise TypeError('%s cannot be merged into a %s' % (
                type(src).__name__, type(dst).__name__))
        super(StringTrie, cls)._merge_impl(dst, src, overwrite=overwrite)

    def __str__(self) -> str:
        if not self:
            return '%s(separator=%s)' % (type(self).__name__, self._separator)
        return '%s(%s, separator=%s)' % (
            type(self).__name__, self._str_items(), self._separator)

    def __repr__(self) -> str:
        return '%s([%s], separator=%r)' % (
            type(self).__name__, self._str_items('(%r, %r)'), self._separator)

    def _eq_impl(self, other: _t.Self) -> bool | _types.NotImplementedType:
        # If separators differ, fall back to slow generic comparison.  This is
        # because we want StringTrie(foo/bar.baz: 42, separator=/) compare equal
        # to StringTrie(foo/bar.baz: 42, separator=.) even though they have
        # different trie structure.
        if self._separator != other._separator:  # pylint: disable=protected-access
            return NotImplemented  # type: ignore[no-any-return]
        return super()._eq_impl(other)

    def _path_from_key(self, key: str) -> _t.Sequence[str]:
        return key.split(self._separator)

    def _key_from_path(self, path: _t.Iterable[str]) -> str:
        return self._separator.join(path)


class PrefixSet(_t.Generic[K, S], _abc.MutableSet[K]):
    """A set of prefixes.

    :class:`pygtrie.PrefixSet` works similar to a normal set except it is said
    to contain a key if the key or it's prefix is stored in the set.  For
    instance, if "foo" is added to the set, the set contains "foo" as well as
    "foobar".

    The set supports addition of elements but does *not* support removal of
    elements.  This is because there's no obvious consistent and intuitive
    behaviour for element deletion.
    """

    def __init__(self,
                 iterable: _t.Iterable[K]=(),
                 factory: _t.Callable[..., Trie[K, bool, S]]=Trie,
                 **kwargs: _t.Any):
        """Initialises the prefix set.

        Args:
            iterable: A sequence of keys to add to the set.
            factory: A function used to create a trie used by the
                    :class:`pygtrie.PrefixSet`.
            kwargs: Additional keyword arguments passed to the factory function.
        """
        super().__init__()
        self._trie = factory(**kwargs)
        for key in iterable:
            self.add(key)

    def copy(self) -> _t.Self:
        """Returns a shallow copy of the object."""
        # pylint: disable=protected-access
        cpy = self.__class__()
        cpy.__dict__ = self.__dict__.copy()
        cpy._trie = self._trie.copy()
        return cpy

    def __copy__(self) -> _t.Self:
        return self.copy()

    def __deepcopy__(self, memo: _t.Any) -> _t.Self:
        # pylint: disable=protected-access
        cpy = self.__class__()
        cpy.__dict__ = self.__dict__.copy()
        cpy._trie = self._trie.__deepcopy__(memo)
        return cpy

    def clear(self) -> None:
        """Removes all keys from the set."""
        self._trie.clear()

    def __contains__(self, key: K) -> bool:  # type: ignore[override]
        """Checks whether set contains key or its prefix."""
        return self._trie.shortest_prefix(key).get(False)

    def __iter__(self) -> _t.Iterator[K]:
        """Return iterator over all prefixes in the set.

        See :func:`PrefixSet.iter` method for more info.
        """
        return self._trie.iterkeys()

    def iter(self, prefix: K | _Sentinel=_SENTINEL) -> _t.Iterator[K]:
        """Iterates over all keys in the set optionally starting with a prefix.

        Since a key does not have to be explicitly added to the set to be an
        element of the set, this method does not iterate over all possible keys
        that the set contains, but only over the shortest set of prefixes of all
        the keys the set contains.

        For example, if "foo" has been added to the set, the set contains also
        "foobar", but this method will *not* iterate over "foobar".

        If ``prefix`` argument is given, method will iterate over keys with
        given prefix only.  The keys yielded from the function if prefix is
        given does not have to be a subset (in mathematical sense) of the keys
        yielded when there is not prefix.  This happens, if the set contains
        a prefix of the given prefix.

        For example, if only "foo" has been added to the set, iter method called
        with no arguments will yield "foo" only.  However, when called with
        "foobar" argument, it will yield "foobar" only.
        """
        if not _is_not_sentinel(prefix):
            return iter(self)
        if self._trie.has_node(prefix):
            return self._trie.iterkeys(prefix=prefix)
        if prefix in self:
            # Make sure the type of returned keys is consistent.
            # pylint: disable=protected-access
            key = self._trie._key_from_path(self._trie._path_from_key(prefix))
            return iter((key,))
        return iter(())

    def __len__(self) -> int:
        """Returns number of keys stored in the set.

        Since a key does not have to be explicitly added to the set to be an
        element of the set, this method does not count over all possible keys
        that the set contains (since that would be infinity), but only over the
        shortest set of prefixes of all the keys the set contains.

        For example, if "foo" has been added to the set, the set contains also
        "foobar", but this method will *not* count "foobar".
        """
        return len(self._trie)

    def add(self, value: K) -> None:
        """Adds given value to the set.

        If the set already contains prefix of the value being added, this
        operation has no effect.  If the value being added is a prefix of some
        existing values in the set, those values are deleted and replaced by
        a single entry for the value being added.

        For example, if the set contains value "foo" adding a value "foobar"
        does not change anything.  On the other hand, if the set contains values
        "foobar" and "foobaz", adding a value "foo" will replace those two
        values with a single value "foo".

        This makes a difference when iterating over the values or counting
        number of values.  Counter intuitively, adding of a value can *decrease*
        size of the set.

        Args:
            value: Value to add.
        """
        # We're friends with Trie;  pylint: disable=protected-access
        self._trie._set_node_if_no_prefix(value)

    def discard(self, value: K) -> _t.Never:
        """Raises NotImplementedError."""
        raise NotImplementedError(
            'Removing values from PrefixSet is not implemented.')

    def remove(self, value: K) -> _t.Never:
        """Raises NotImplementedError."""
        raise NotImplementedError(
            'Removing values from PrefixSet is not implemented.')

    def pop(self) -> _t.Never:
        """Raises NotImplementedError."""
        raise NotImplementedError(
            'Removing values from PrefixSet is not implemented.')
