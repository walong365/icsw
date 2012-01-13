#!/bin/bash

function slp() {
    WT=${1:-30}
    echo "sleep $WT secs"
    sleep $WT
}

rm -rf /tmp/*.fwtest /tmp/*test*

unregister_file_watch id:x2
unregister_file_watch id:x3
mkdir /tmp/testdir
register_file_watch mode:content id:x2 dir:/tmp/testdir match:*.fwtest timeout:4 target_server:localhost target_port:22 poll:true
register_file_watch mode:timeout id:x3 dir:/tmp/testdir timeout:60 action:/bin/true

slp 3

mkdir /tmp/testdir/bla
mkdir /tmp/testdir/bla/d
touch /tmp/a.fwtest
echo "fwt0" > /tmp/a.fwtest
slp
echo "fwt1" > /tmp/testdir/a2.fwtest
slp 
echo "fwt2" > /tmp/testdir/a3.fwtest
slp
echo "fwt2" > /tmp/testdir/a2.fwtest
slp
mkdir /tmp/testdir/d
echo "fwt2" > /tmp/testdir/d/a5.fwtest
slp
echo "fwt3" > /tmp/a.fwtest
rm /tmp/a.fwtest
echo "fwt4" > /tmp/a.fwtest

# touch /tmp/testfile

slp

rm -rf /tmp/testdir

slp 1

unregister_file_watch id:x2
unregister_file_watch id:x3
# slp
