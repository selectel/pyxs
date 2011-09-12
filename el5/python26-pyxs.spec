%define debug_package %{nil}

Summary:    	Pure Python bindings to XenStore
Name:	    	python26-pyxs
Version:    	0.2
Release:    	1.selectel%{?dist}
Vendor:	    	Selectel
License:    	LGPL
Group:	    	Development/Libraries/Python
URL:            http://docs.selectel.org/pyxs
Source0:        http://scm.selectel.org/pyxs.git/snapshot/pyxs-%{version}.tar.gz
Requires:       python26
BuildArch:      noarch
BuildRequires:  python26-setuptools
BuildRoot:      %{_tmppath}/pyxs-%{version}-%{release}-root-%(%{__id_u} -n)

%description
A Python library for working with XenStore database.

%prep
%setup -q -n pyxs-%{version}

%build
/usr/bin/python2.6 setup.py build

%install
/usr/bin/python2.6 setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%doc AUTHORS
%doc CHANGES
%doc README
%defattr(-,root,root,-)

%changelog
* Thu Sep 1 2011  Sergei Lebedev <lebedev@selectel.ru>
- Initial packaging for CentOS
