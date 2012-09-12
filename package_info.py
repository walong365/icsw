#!/usr/bin/python-init -Ot
# base classes and functions for dumping out package Metadata
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2003 Duke University

# $Id: dumpMetadata.py,v 1.10 2004/01/18 21:43:05 skvidal Exp $

import sys
import os
import os.path
import md5
import sha
import types
import struct
import stat
import rpm_module
import cPickle
import time
import logging_tools

rpm = rpm_module.get_rpm_module()

class RpmMetaData:
    def __init__(self, filename):
        try:
            stats = os.stat(filename)
            self.size = stats[6]
            self.mtime = stats[8]
            del stats
        except OSError, e:
            raise rpm_module.RPMError, "Error Stat'ing file %s" % filename
        
        self.relativepath = filename
        self.header = rpm_module.return_package_header(filename)
        self.filenames = []
        self.dirnames = []
        self.ghostnames = []
        self.genFileLists()
    def arch(self):
        if self["sourcepackage"] == 1:
            return "src"
        else:
            return self["arch"]
    def _correctFlags(self, flags):
        returnflags=[]
        if flags:
            if type(flags) != type([]):
                flags = [flags]
            for flag in flags:
                if flag:
                    returnflags.append(flag & 0xf)
                else:
                    returnflags.append(flag)
        return returnflags
    def beautifyFlags(self, flags):
        return [{0 : "None",
                 2 : "<",
                 4 : ">",
                 6 : "<>",
                 8 : "=",
                 10 : "<=",
                 12 : ">="}[x] for x in flags]
    def _correctVersion(self, vers):
        if vers is None:
            returnvers = [(None, None, None)]
        else:
            returnvers = []
            if type(vers) != type([]):
                vers = [vers]
            for ver in vers:
                if ver:
                    returnvers.append(self._stringToVersion(ver))
                else:
                    returnvers.append((None, None, None))
        return returnvers
    def _stringToVersion(self, strng):
        s1 = strng.split(":", 1)
        if len(s1) == 1:
            epoch, sub_str = ("0", strng)
        else:
            epoch, sub_str = s1
        s2 = sub_str.split("-", 1)
        if len(s2) == 1:
            version, release = (sub_str, "")
        else:
            version, release = s2
        epoch, version, release = tuple([x or None for x in [epoch, version, release]])
        return (epoch, version, release)
    ###########
    # Title: Remove duplicates from a sequence
    # Submitter: Tim Peters 
    # From: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52560                      
        
    def _uniq(self,s):
        """Return a list of the elements in s, but without duplicates.
    
        For example, unique([1,2,3,1,2,3]) is some permutation of [1,2,3],
        unique("abcabc") some permutation of ["a", "b", "c"], and
        unique(([1, 2], [2, 3], [1, 2])) some permutation of
        [[2, 3], [1, 2]].
    
        For best speed, all sequence elements should be hashable.  Then
        unique() will usually work in linear time.
    
        If not possible, the sequence elements should enjoy a total
        ordering, and if list(s).sort() doesn't raise TypeError it's
        assumed that they do enjoy a total ordering.  Then unique() will
        usually work in O(N*log2(N)) time.
    
        If that's not possible either, the sequence elements must support
        equality-testing.  Then unique() will usually work in quadratic
        time.
        """
    
        n = len(s)
        if n == 0:
            return []
    
        # Try using a dict first, as that's the fastest and will usually
        # work.  If it doesn't work, it will usually fail quickly, so it
        # usually doesn't cost much to *try* it.  It requires that all the
        # sequence elements be hashable, and support equality comparison.
        u = {}
        try:
            for x in s:
                u[x] = 1
        except TypeError:
            del u  # move on to the next method
        else:
            return u.keys()
    
        # We can't hash all the elements.  Second fastest is to sort,
        # which brings the equal elements together; then duplicates are
        # easy to weed out in a single pass.
        # NOTE:  Python's list.sort() was designed to be efficient in the
        # presence of many duplicate elements.  This isn't true of all
        # sort functions in all languages or libraries, so this approach
        # is more effective in Python than it may be elsewhere.
        try:
            t = list(s)
            t.sort()
        except TypeError:
            del t  # move on to the next method
        else:
            assert n > 0
            last = t[0]
            lasti = i = 1
            while i < n:
                if t[i] != last:
                    t[lasti] = last = t[i]
                    lasti += 1
                i += 1
            return t[:lasti]
        # Brute force is all that's left.
        u = []
        for x in s:
            if x not in u:
                u.append(x)
        return u
    def __getitem__(self, key):
        return self.header[key]
    def listTagByName(self, tag):
        """take a tag that should be a list and make sure it is one"""
        data = self[tag]
        if data is None:
            lst = []
        elif type(data) == type([]):
            lst = data
        else:
            lst = [data]
        return lst
    def epoch(self):
        if self["epoch"] is None:
            return 0
        else:
            return self["epoch"]
    def genFileLists(self):
        """produces lists of dirs and files for this header in two lists"""
        files = self.listTagByName("filenames")
        fileflags = self.listTagByName("fileflags")
        filemodes = self.listTagByName("filemodes")
        filetuple = zip(files, filemodes, fileflags)
        for (file, mode, flag) in filetuple:
            if stat.S_ISDIR(mode):
                self.dirnames.append(file)                
            else:
                if (flag & 64): 
                    self.ghostnames.append(file)
                else:
                    self.filenames.append(file)
    def depsList(self):
        """returns a list of tuples of dependencies"""
        # these should probably compress down duplicates too
        lst = []
        names = self[rpm.RPMTAG_REQUIRENAME]
        tmpflags = self[rpm.RPMTAG_REQUIREFLAGS]
        flags = self.beautifyFlags(self._correctFlags(tmpflags))
        ver = self._correctVersion(self[rpm.RPMTAG_REQUIREVERSION])
        if names is not None:
            lst = zip(names, flags, ver)
        return self._uniq(lst)
    def obsoletesList(self):
        lst = []
        names = self[rpm.RPMTAG_OBSOLETENAME]
        tmpflags = self[rpm.RPMTAG_OBSOLETEFLAGS]
        flags = self._correctFlags(tmpflags)
        ver = self._correctVersion(self[rpm.RPMTAG_OBSOLETEVERSION])
        if names is not None:
            lst = zip(names, flags, ver)
        return self._uniq(lst)
    def conflictsList(self):
        lst = []
        names = self[rpm.RPMTAG_CONFLICTNAME]
        tmpflags = self[rpm.RPMTAG_CONFLICTFLAGS]
        flags = self._correctFlags(tmpflags)
        ver = self._correctVersion(self[rpm.RPMTAG_CONFLICTVERSION])
        if names is not None:
            lst = zip(names, flags, ver)
        return self._uniq(lst)
    def providesList(self):
        lst = []
        names = self[rpm.RPMTAG_PROVIDENAME]
        tmpflags = self[rpm.RPMTAG_PROVIDEFLAGS]
        flags = self._correctFlags(tmpflags)
        ver = self._correctVersion(self[rpm.RPMTAG_PROVIDEVERSION])
        if names is not None:
            lst = zip(names, flags, ver)
        return self._uniq(lst)
    def changelogLists(self):
        lst = []
        names = self.listTagByName("changelogname")
        times = self.listTagByName("changelogtime")
        texts = self.listTagByName("changelogtext")
        if len(names) > 0:
            lst = zip(names, times, texts)
        return lst
    
class simpleCallback:
    def __init__(self):
        self.fdnos = {}

    def callback(self, what, amount, total, mydata, wibble):
##    	"""what -- callback type, 
##    amount -- bytes processed
## 	   total -- total bytes
##            mydata -- package key (hdr, path)
## 	   wibble -- user data - unused here"""
        #print what
        if what == rpm.RPMCALLBACK_TRANS_START:
            print "start"

        elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            hdr, path = mydata
            print "Installing %s\r" % (hdr["name"])
            fd = os.open(path, os.O_RDONLY)
            nvr = '%s-%s-%s' % ( hdr['name'], hdr['version'], hdr['release'] )
            self.fdnos[nvr] = fd
            return fd

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            print "close"
            hdr, path = mydata
            nvr = '%s-%s-%s' % ( hdr['name'], hdr['version'], hdr['release'] )
            os.close(self.fdnos[nvr])

        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            hdr, path = mydata
            #print "%s:  %.5s%% done\r" % (hdr["name"], (float(amount) / total) * 100)

my_arch = rpm_module.get_canonical_architecture()
s_time = time.time()
#print "a"
ts = rpm_module.get_TransactionSet()
#print "a",dir(ts),"\n".join([str((x, getattr(rpm,x))) for x in dir(rpm) if x.count("RPMPROB")])
#sys.exit(0)

rpm.setVerbosity(rpm.RPMLOG_ERR)
#db_match = ts.dbMatch()
#print dir(ts),dir(db_match),db_match.count()

hdr = rpm_module.return_package_header(sys.argv[1])
#ts.setProbFilter(rpm.RPMPROB_FILTER_IGNOREARCH|rpm.RPMPROB_FILTER_IGNOREOS)
# -U behaviour
# ts.setProbFilter(rpm.RPMPROB_FILTER_REPLACEOLDFILES)
# --force behaviour
# ts.setProbFilter(rpm.RPMPROB_FILTER_REPLACEPKG|rpm.RPMPROB_FILTER_REPLACEOLDFILES|rpm.RPMPROB_FILTER_OLDPACKAGE)
#ts.setProbFilter(|rpm.RPMPROB_FILTER_REPLACEPKG|rpm.RPMPROB_FILTER_REPLACEOLDFILES)
ts.addInstall(hdr,(hdr,sys.argv[1]), "u")
cb = simpleCallback()
print rpm_module.arch_norm(my_arch, hdr["arch"])
print ts.check(cb.callback)
print ts.run(cb.callback,'')
sys.exit(0)
#while 1:
while 1:
    hdr= db_match.next()
    print db_match.instance(),dir(db_match)
    if hdr:
        #print "c"
        #print dir(hdr)
        new_rpm = rpm_module.rpm_package(hdr, "pcdo")
        #print new_rpm.provides_list
        #print new_rpm.depends_list
        #print new_rpm.conflicts_list
        #print new_rpm.obsoletes_list
        print new_rpm.bi
print time.time() - s_time
sys.exit(0)
#print ts.dbMatch()
#print ts.dbMatch()
#print "\n".join([str((x, getattr(rpm, x))) for x in dir(rpm) if x.count("SENSE")])
x = RpmMetaData(sys.argv[1])
print x.arch()
print x.epoch()
print x.providesList()
#print "\n".join([str(y) for y in x.depsList()])
#print "\n".join([str(y) for y in x.changelogLists()])
#print dir(x.header),x.header.dsFromHeader(),x.header.dsOfHeader(),x.header.fiFromHeader()
#print len(x.header.unload()), len(x.header.rhnUnload())
#print len(cPickle.dumps(x.header))
