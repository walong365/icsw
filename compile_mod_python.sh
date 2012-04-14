#!/bin/bash
# CentOS 4 (BACA): ./configure --build=i686-redhat-linux-gnu --host=i686-redhat-linux-gnu --target=i386-redhat-linux-gnu --program-prefix= --prefix=/usr --exec-prefix=/usr --bindir=/usr/bin --sbindir=/usr/sbin --sysconfdir=/etc --datadir=/usr/share --includedir=/usr/include --libdir=/usr/lib --libexecdir=/usr/libexec --localstatedir=/var --sharedstatedir=/usr/com --mandir=/usr/share/man --infodir=/usr/share/info --with-apxs=/usr/sbin/apxs
# hack: ln -s .libs/mod_python.so . in src directory

if true ; then
    unset LD_LIBRARY_PATH
    ./configure --with-apxs=/usr/sbin/apxs2
else
    export LD_LIBRARY_PATH=/opt/python-init/lib
    ./configure --with-python=/opt/python-init/bin/python --with-apxs=/usr/sbin/apxs2
fi
make
make install

