.. _tutorial:

Tutorial
========


Basics
------

Using :mod:`pyxs` is easy! The only class you need to import is
:class:`~pyxs.client.Client`. It provides a simple straightforward API
to XenStore content with a bit of Python's syntactic sugar here and
there.

Generally, if you just need to fetch or update some XenStore items you
can do::

   >>> from pyxs import Client
   >>> with Client() as c:
   ...     c[b"/local/domain/0/name"] = b"Ziggy"
   ...     c[b"/local/domain/0/name"]
   b'Ziggy'

Using :class:`~pyxs.client.Client` without the ``with`` statement is
possible, albeit, not recommended:

  >>> c = Client()
  >>> c.connect()
  >>> c[b"/local/domain/0/name"] = b"It works!"
  >>> c.close()

The reason for preferring a context manager is simple: you don't have
to DIY. The context manager will make sure that a started transaction
was either rolled back or committed and close the underlying XenStore
connection afterwards.

Transactions
------------

Transactions allow you to operate on an isolated copy of XenStore tree
and merge your changes back atomically on commit. Keep in mind, however,
that changes made within a transaction become available to other XenStore
clients only if and when committed.  Here's an example::

    >>> with Client() as c:
    ...     c.transaction()
    ...     c[b"/foo/bar"] = b"baz"
    ...     c.commit()  # !
    ...     print(c[b"/foo/bar"])
    b'baz'

The line with an exclamation mark is a bit careless, because it
ignores the fact that committing a transaction might fail. A more
robust way to commit a transaction is by using a loop::

    >>> with Client() as c:
    ...     success = False
    ...     while not success:
    ...         c.transaction()
    ...         c[b"/foo/bar"] = b"baz"
    ...         success = c.commit()

You can also abort the current transaction by calling
:meth:`~pyxs.client.Client.rollback`.

Events
------

When a new path is created or an existing path is modified, XenStore
fires an event, notifying all watching clients that a change has been
made.  :mod:`pyxs` implements watching via the :class:`Monitor`
class. To watch a path create a monitor
:meth:`~pyxs.client.Client.monitor` and call
:meth:`~pyxs.client.Monitor.watch` with a path you want to watch and a
unique token. Right after that the monitor will start to accumulate
incoming events.  You can iterate over them via
:meth:`~pyxs.client.Monitor.wait`::

    >>> with Client() as c:
    ...    m = c.monitor()
    ...    m.watch(b"/foo/bar", b"a unique token")
    ...    next(m.wait())
    Event(b"/foo/bar", b"a unique token")

XenStore has a notion of *special* paths, which start with ``@`` and
are reserved for special occasions:

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

Events for both special and ordinary paths are simple two element
tuples, where the first element is always `event target` -- a path
which triggered the event and second is a token passed to
:meth:`~pyxs.client.Monitor.watch`. A rather unfortunate consequence
of this is that you can't get `domid` of the domain, which triggered
@introduceDomain or @releaseDomain from the received event.


Compatibility API
-----------------

:mod:`pyxs` also provides a compatibility interface, which mimics that
of ``xen.lowlevel.xs`` --- so you don't have to change
anything in the code to switch to :mod:`pyxs`::

   >>> from pyxs import xs
   >>> handle = xs()
   >>> handle.read("0", b"/local/domain/0/name")
   b'Domain-0'
   >>> handle.close()
