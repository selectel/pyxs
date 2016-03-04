.. _api:


API reference
=============

Client and Monitor
------------------

.. autoclass:: pyxs.client.Client
   :members:

.. autoclass:: pyxs.client.Monitor
   :members:

.. autofunction:: pyxs.monitor

Exceptions
----------

.. autoclass:: pyxs.exceptions.PyXSError

.. autoclass:: pyxs.exceptions.InvalidOperation

.. autoclass:: pyxs.exceptions.InvalidPayload

.. autoclass:: pyxs.exceptions.InvalidPath

.. autoclass:: pyxs.exceptions.InvalidPermission

.. autoclass:: pyxs.exceptions.ConnectionError

.. autoclass:: pyxs.exceptions.UnexpectedPacket

Internals
---------

.. autoclass:: pyxs.client.Router
   :members:

.. autoclass:: pyxs.connection.PacketConnection
   :members:

.. autoclass:: pyxs.connection.XenBusConnection

.. autoclass:: pyxs.connection.UnixSocketConnection

.. autoclass:: pyxs._internal.Packet

.. autodata:: pyxs._internal.Op
