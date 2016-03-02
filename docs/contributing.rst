Contributing
============

Submitting a bug report
-----------------------

In case you experience issues using ``pyxs``, do not hesitate to report it
to the `Bug Tracker <https://github.com/hmmlearn/hmmlearn/issues>`_ on
GitHub.

Setting up development environment
----------------------------------

Writing a XenStore client library without having access to a running XenStore
instance can be troublesome. Luckily, there is a way to setup a development
using VirtualBox.

1. Create a VM running Ubuntu 14.04 or later.
2. `Install <http://www.skjegstad.com/blog/2015/01/19/mirageos-xen-virtualbox>`_
   Xen hypervisor: ``sudo apt-get install xen-hypervisor-4.4-amd64``.
3. `Configure <http://stackoverflow.com/a/10532299/262432>`_ VM for SSH access.
4. Done! You can now ``rsync`` your changes to the VM and run the tests.

Style guide
-----------

``pyxs`` follows Pocoo style guide. Please
`read it <http://www.pocoo.org/internal/styleguide>`_ before you start
implementing your changes.
