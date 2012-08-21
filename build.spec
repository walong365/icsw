Name: initcore
Version: 1.0.6
Summary: The core init python package (alfresco, web, ...)
Release: 1
Group: Development/Languages/Python
License: GPL
Requires: python-init django-init
Source: initcore.tgz
Packager: Christoph Sieghart <sieghart@init.at>
Vendor: init.at Informationstechnologie GmbH
BuildRoot: %{_tmppath}/%{name}-%{version}-build

%description
The core init python package (alfresco, web, ...)

%prep
%setup -c

%build
%{__make} %{?_smp_mflags}

%install
%{__make} DESTDIR=${RPM_BUILD_ROOT} install

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root)
/opt/python-init/lib/python2.7/site-packages/initcore/
/opt/python-init/lib/python2.7/site-packages/initcore-%{version}-py2.7.egg-info
