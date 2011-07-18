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

    >>> c = Client()
    >>> with c.transaction() as t:
    ...    t["/foo/bar"] = "baz"
    ...    t.transaction_end(commit=True)

However, the last line is completely optional, since the default behaviour
is to commit everything on context manager exit. Note that **changes made
inside a transaction aren't available to other XenStore clients unless you
commit them**.


Events
------

When a new path is created or an existing path is modified, XenStore
fires an event, notifying all watchers that a change has occurred. To
watch a path, you have to call :meth:`~pyxs.client.Client.watch`
with a path you want to watch and a token, unique for that path
within the active transaction. After that incoming events can be
fetched by calling :meth:`~pyxs.client.Client.wait`::

    >>> with Client() as c:
    ...    c.watch("/foo/bar", "a unique token")
    ...    c.wait()
    Event("/foo/bar", "a unique token")

XenStore also has a notion of `special` paths, which are reserved for
special occasions:

    ================  ================================================
    Path              Description
    ----------------  ------------------------------------------------
    @introduceDomain  Fired when a **new** domain is introduced to
                      XenStore -- you can also introduce domains
                      yourself with a
                      :meth:`~pyxs.client.Client.introduce_domain`
                      call, but in most of the cases, ``xenstored``
                      will do that for you.
    @releaseDomain    Fired when XenStore is no longer communicating
                      with a domain, see
                      :meth:`~pyxs.client.Client.release_domain`.
    ================  ================================================

Events for both `special` and ordinary paths are simple two element
tuples, where the first element is always `event target` -- a path
which triggered the event and second is a token, you've passed to
:meth:`~pyxs.client.Client.watch`. A nasty consequence of this is that
you can't get `domid` of the domain, which triggered
``@introduceDomain`` or ``@releaseDomain`` from the received event.


Y U SO LAZY DAWG
----------------

:mod:`pyxs` also provides a compatibility interface, which mimics the
ones of ``xen.lowlevel.xs`` -- so you don't have to change **anything**
in the code to switch to :mod:`pyxs`::

   >>> from pyxs import xs
   >>> xs = xs()
   >>> xs.read(0, "/local/domain/0/name")
   'Domain0'
