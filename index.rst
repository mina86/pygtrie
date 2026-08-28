pygtrie
=======

.. automodule:: pygtrie

Installation
------------

To install pygtrie, simply run::

    pip install pygtrie

or by adding line such as::

    pygtrie == 2.*

to project’s `requirements file
<https://pip.pypa.io/en/latest/user_guide/#requirements-files>`_.

Trie classes
------------

.. autoclass:: pygtrie.Trie
   :members:
   :private-members: _path_from_key, _key_from_path

.. autoclass:: pygtrie.CharTrie
   :members:

.. autoclass:: pygtrie.StringTrie
   :members:

.. autoclass:: pygtrie._Step
   :members:

.. autoclass:: pygtrie._NoneStep
   :members:

PrefixSet class
---------------

.. autoclass:: pygtrie.PrefixSet
   :members:

Custom exceptions
-----------------

.. autoclass:: pygtrie.ShortKeyError
   :members:

Typing classes
---------------

.. autoclass:: pygtrie.NodeFactory
   :members:


.. include:: version-history.rst
