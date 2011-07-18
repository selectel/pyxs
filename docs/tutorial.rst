.. _tutorial:

Tutorial
========


Basics
------

The only class you need to import from :mod:`pyxs` (unless you're up
to some spooky stuff) is :class:`~pyxs.client.Client` -- it provides
a simple straightforward API to access XenStore content, adding a bit
of Python's syntactic Magic here and there. Generally, if you just need
to get or update some XenStore items you can do::

   >>> from pyxs import Client
   >>> with Client() as c:
   ...     c["/local/domain/0/name"] = "Domain0"
   ...     c["/local/domain/0/name"]
   'Domain0'

.. note:: Even though :class:`~pyxs.client.Client` does support
          :func:`dict`-like lookups, they have nothing else in common
          -- for instance there's no :meth:`Client.get` currently.


Transactions
------------

If you're already familiar with XenStore features, you probably know that
it has support for transactions; which allow you to operate on a separate
copy of the XenStore tree. After a transaction is committed the changes
are merged back into the main tree::

    >>> from pyxs import Client
    >>> c = Client()
    >>> with c.transaction() as t:
    ...    t["/foo/bar"] = "baz"
    ...    t.transaction_end(commit=True)

However, the last line is completely optional, since the default behaviour
is to commit everything on context manager exit. Note that **changes made
inside a transaction aren't available to other XenStore clients unless you
commit them**.


Y U SO LAZY DAWG
----------------

:mod:`pyxs` also provides a compatibility interface, which mimics the ones
of ``xen.lowlevel.xs`` -- so you don't have to change **anthing** in the
code to switch to :mod:`pyxs`::

   >>> from pyxs import xs
   >>> xs = xs()
   >>> xs.read(0, "/local/domain/0/name")
   'Domain0'
