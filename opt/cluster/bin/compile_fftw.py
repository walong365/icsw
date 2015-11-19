#!/usr/bin/python-init -Otu
#
# Copyright (c) 2007,2008,2009 Andreas Lang-Nevyjel, init.at
#
# this file is part of cbc-tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" compiles fftw """

import commands
import optparse
import os
import os.path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import cluster_module_tools

from initat.tools import compile_tools, cpu_database, logging_tools, rpm_build_tools

FFTW_VERSION_FILE = "/opt/cluster/share/fftw_versions"


class my_opt_parser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self)
        # check for 64-bit Machine
        self.mach_arch = os.uname()[4]
        if self.mach_arch in ["x86_64", "ia64"]:
            is_64_bit = True
        else:
            is_64_bit = False
        self._read_fftw_versions()
        target_dir = "/opt/libs/"
        fc_choices = sorted(["GNU",
                             "INTEL",
                             "PATHSCALE"])
        self.cpu_id = cpu_database.get_cpuid()
        self.add_option("-c", type="choice", dest="fcompiler", help="Set Compiler type, options are %s [%%default]" % (", ".join(fc_choices)), action="store", choices=fc_choices, default="GNU")
        self.add_option("--fpath", type="string", dest="fcompiler_path", help="Compiler Base Path, for instance /opt/intel/compiler-9.1 [%default]", default="NOT_SET")
        self.add_option("-o", type="choice", dest="fftw_version", help="Choose FFTW Version, possible values are %s [%%default]" % (", ".join(self.version_dict.keys())), action="store", choices=self.version_dict.keys(), default=self.highest_version)
        self.add_option("-d", type="string", dest="target_dir", help="Sets target directory [%default]", default=target_dir, action="store")
        self.add_option("--extra", type="string", dest="extra_settings", help="Sets extra options for configure, i.e. installation directory and package name [%default]", action="store", default="")
        self.add_option("--extra-filename", type="string", dest="extra_filename", help="Sets extra filename string [%default]", action="store", default="")
        self.add_option("--arch", type="str", dest="arch", help="Set package architecture [%default]", default="")
        self.add_option("--log", dest="include_log", help="Include log of make-command in README [%default]", action="store_true", default=False)
        self.add_option("-v", dest="verbose", help="Set verbose level [%default]", action="store_true", default=False)
        self.add_option("--release", dest="release", type="str", help="Set release [%default]", default="1")
        if is_64_bit:
            # add option for 32-bit goto if machine is NOT 32 bit
            self.add_option("--32", dest="use_64_bit", help="Set 32-Bit build [%default]", action="store_false", default=True)
        else:
            self.add_option("--64", dest="use_64_bit", help="Set 64-Bit build [%default]", action="store_true", default=False)
    def parse(self):
        options, args = self.parse_args()
        if args:
            print "Additional arguments found, exiting"
            sys.exit(0)
        self.options = options
        self._check_compiler_settings()
        self.package_name = "fftw-%s-%s-%s-%s%s" % (self.options.fftw_version,
                                                    self.options.fcompiler,
                                                    self.small_version,
                                                    self.options.use_64_bit and "64" or "32",
                                                    self.options.extra_filename and "-%s" % (self.options.extra_filename.strip()) or "")
        self.fftw_dir = "%s/%s" % (self.options.target_dir,
                                   self.package_name)
    def _check_compiler_settings(self):
        self.add_path_dict = {}
        if self.options.fcompiler == "GNU":
            self.compiler_dict = {"CC"  : "gcc",
                                  "CXX" : "g++",
                                  "F77" : "gfortran",
                                  "FC"  : "gfortran"}
            stat, out = commands.getstatusoutput("gcc --version")
            if stat:
                raise ValueError, "Cannot get Version from gcc (%d): %s" % (stat, out)
            self.small_version = out.split(")")[1].split()[0]
            self.compiler_version_dict = {"GCC" : out}
        elif self.options.fcompiler == "INTEL":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = {"LD_LIBRARY_PATH" : ["%s/lib" % (self.options.fcompiler_path)],
                                      "PATH"            : ["%s/bin" % (self.options.fcompiler_path)]}
                self.compiler_dict = {"CC"  : "icc",
                                      "CXX" : "icpc",
                                      "F77" : "ifort",
                                      "FC"  : "ifort"}
                ifort_out_lines, small_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path)
                if not small_version:
                    sys.exit(-1)
                self.small_version = small_version
                ifort_out = "\n".join(ifort_out_lines)
                self.compiler_version_dict = {"ifort" : ifort_out}
                stat, icc_out = commands.getstatusoutput("%s/bin/icc -V" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError, "Cannot get Version from icc (%d): %s" % (stat, icc_out)
                self.compiler_version_dict = {"ifort" : ifort_out,
                                              "icc"   : icc_out}
            else:
                raise IOError, "Compiler base path '%s' for compiler setting %s is not a directory" % (self.options.fcompiler_path,
                                                                                                       self.options.fcompiler)
        elif self.options.fcompiler == "PATHSCALE":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = {"LD_LIBRARY_PATH": ["%s/lib" % (self.options.fcompiler_path)],
                                      "PATH"           : ["%s/bin" % (self.options.fcompiler_path)]}
                self.compiler_dict = {"CC"  : "pathcc",
                                      "CXX" : "pathCC",
                                      "F77" : "pathf95",
                                      "FC"  : "pathf95"}
                stat, pathf95_out = commands.getstatusoutput("%s/bin/pathf95 -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError, "Cannot get Version from pathf95 (%d): %s" % (stat, pathf95_out)
                self.small_version = pathf95_out.split("\n")[0]
                self.compiler_version_dict = {"pathf95" : pathf95_out}
                stat, pathcc_out = commands.getstatusoutput("%s/bin/pathcc -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError, "Cannot get Version from pathcc (%d): %s" % (stat, pathcc_out)
                self.compiler_version_dict = {"pathf95" : pathf95_out,
                                              "pathcc"   : pathcc_out}
            else:
                raise IOError, "Compiler base path '%s' for compiler setting %s is not a directory" % (self.options.fcompiler_path,
                                                                                                       self.options.fcompiler)
        else:
            raise ValueError, "Compiler settings %s unknown" % (self.options.fcompiler)
    def _read_fftw_versions(self):
        if os.path.isfile(FFTW_VERSION_FILE):
            version_lines = [line.strip().split() for line in file(FFTW_VERSION_FILE, "r").read().split("\n") if line.strip()]
            self.version_dict = dict([(key, value) for key, value in version_lines])
            vers_dict = dict([(tuple([part.isdigit() and int(part) or part for part in key.split(".")]), key) for key in self.version_dict.keys()])
            vers_keys = sorted(vers_dict.keys())
            self.highest_version = vers_dict[vers_keys[-1]]
        else:
            raise IOError, "No %s found" % (FFTW_VERSION_FILE)
    def get_compile_options(self):
        return "\n".join([" - build_date is %s" % (time.ctime()),
                          " - fftw Version is %s, cpuid is %s" % (self.options.fftw_version,
                                                                  self.cpu_id),
                          " - Compiler is %s, Compiler Base path is %s" % (self.options.fcompiler,
                                                                           self.options.fcompiler_path),
                          " - small_version is %s" % (self.small_version),
                          " - source package is %s, target directory is %s" % (self.version_dict[self.options.fftw_version],
                                                                               self.fftw_dir),
                          " - extra_settings for configure: %s" % (self.options.extra_settings),
                          "compiler settings: %s" % ", ".join(["%s=%s" % (key, value) for key, value in self.compiler_dict.iteritems()]),
                          "add_path_dict    : %s" % ", ".join(["%s=%s:$%s" % (key, ":".join(value), key) for key, value in self.add_path_dict.iteritems()]),
                          "version info:"] + \
                         ["%s:\n%s" % (key, "\n".join(["    %s" % (line.strip()) for line in value.split("\n")])) for key, value in self.compiler_version_dict.iteritems()])

class fftw_builder(object):
    def __init__(self, parser):
        self.parser = parser
    def build_it(self):
        self.compile_ok = False
        self._init_tempdir()
        if self._untar_source():
            if self._compile_it():
                if self.package_it():
                    self.compile_ok = True
                    self._remove_tempdir()
        if not self.compile_ok:
            print "Not removing temporary directory %s" % (self.tempdir)
    def _init_tempdir(self):
        self.tempdir = tempfile.mkdtemp("_fftw")
    def _remove_tempdir(self):
        print "Removing temporary directory"
        shutil.rmtree(self.tempdir)
        try:
            os.rmdir(self.tempdir)
        except:
            pass
    def _untar_source(self):
        tar_source = self.parser.version_dict[self.parser.options.fftw_version]
        if not os.path.isfile(tar_source):
            print "Cannot find FFTW source %s" % (tar_source)
            success = False
        else:
            print "Extracting tarfile %s ..." % (tar_source),
            tar_file = tarfile.open(tar_source, "r")
            tar_file.extractall(self.tempdir)
            tar_file.close()
            print "done"
            success = True
        return success
    def _compile_it(self):
        num_cores = cpu_database.global_cpu_info(parse=True).num_cores() * 2
        act_dir = os.getcwd()
        os.chdir("%s/fftw-%s" % (self.tempdir, self.parser.options.fftw_version))
        print "Modifying environment"
        for env_name, env_value in self.parser.compiler_dict.iteritems():
            os.environ[env_name] = env_value
        for path_name, path_add_value in self.parser.add_path_dict.iteritems():
            os.environ[path_name] = "%s:%s" % (":".join(path_add_value), os.environ.get(path_name, ""))
        self.time_dict, self.log_dict = ({}, {})
        success = True
        for command, time_name in [("./configure --enable-shared --enable-static --prefix=%s %s" % (self.parser.fftw_dir,
                                                                                                    self.parser.options.extra_settings), "configure"),
                                   ("make -j %d" % (num_cores), "make"),
                                   ("make install", "install")]:
            self.time_dict[time_name] = {"start" : time.time()}
            print "Doing command %s" % (command)
            sp_obj = subprocess.Popen(command.split(), 0, None, None, subprocess.PIPE, subprocess.STDOUT)
            out_lines = []
            while True:
                stat = sp_obj.poll()
                while True:
                    try:
                        new_lines = sp_obj.stdout.next()
                    except StopIteration:
                        break
                    else:
                        if self.parser.options.verbose:
                            print new_lines,
                        if type(new_lines) == type([]):
                            out_lines.extend(new_lines)
                        else:
                            out_lines.append(new_lines)
                if stat is not None:
                    break
            self.time_dict[time_name]["end"] = time.time()
            self.time_dict[time_name]["diff"] = self.time_dict[time_name]["end"] - self.time_dict[time_name]["start"]
            self.log_dict[time_name] = "".join(out_lines)
            if stat:
                print "Something went wrong (%d):" % (stat)
                if not self.parser.options.verbose:
                    print "".join(out_lines)
                success = False
                break
            else:
                print "done, took %s" % (logging_tools.get_diff_time_str(self.time_dict[time_name]["diff"]))
        os.chdir(act_dir)
        return success
    def package_it(self):
        print "Packaging ..."
        info_name = "README.%s" % (self.parser.package_name)
        sep_str = "-" * 50
        readme_lines = [sep_str] + \
            self.parser.get_compile_options().split("\n") + \
            ["Compile times: %s" % (", ".join(["%s: %s" % (key, logging_tools.get_diff_time_str(self.time_dict[key]["diff"])) for key in self.time_dict.keys()])), sep_str, ""]
        if self.parser.options.include_log:
            readme_lines.extend(["Compile logs:"] + \
                                sum([self.log_dict[key].split("\n") + [sep_str] for key in self.log_dict.keys()], []))
        file("%s/%s" % (self.tempdir, info_name), "w").write("\n".join(readme_lines))
        package_name, package_version, package_release = (self.parser.package_name,
                                                          self.parser.options.fftw_version,
                                                          self.parser.options.release)
        # create cluster module file
        cmod = cluster_module_tools.cluster_module(name=package_name,
                                                   version=package_version,
                                                   release=package_release,
                                                   description="FFTW",
                                                   #arch=self.parse
                                                   )
        cmod.add_env_variable(cluster_module_tools.cluster_module_env(name="PATH",
                                                                      mode="append",
                                                                      value="%s/bin" % (self.parser.fftw_dir)))
        cmod.add_env_variable(cluster_module_tools.cluster_module_env(name="LD_LIBRARY",
                                                                      mode="append",
                                                                      value="%s/lib" % (self.parser.fftw_dir)))
        open("%s/cmod" % (self.tempdir), "w").write(cmod.get_xml_representation())
        new_p = rpm_build_tools.build_package()
        if self.parser.options.arch:
            new_p["arch"] = self.parser.options.arch
        new_p["name"] = package_name
        new_p["version"] = package_version
        new_p["release"] = package_release
        new_p["package_group"] = "System/Libraries"
        new_p["inst_options"] = " -p "
        # remove old info if present
        if os.path.isfile("%s/%s" % (self.parser.fftw_dir, info_name)):
            os.unlink("%s/%s" % (self.parser.fftw_dir, info_name))
        content = rpm_build_tools.file_content_list([self.parser.fftw_dir,
                                                     "%s/%s:%s/%s" % (self.tempdir, info_name, self.parser.fftw_dir, info_name),
                                                     "*%s/cmod:/opt/cluster/modules/%s" % (self.tempdir, cmod.get_name())])
        new_p.create_tgz_file(content)
        new_p.write_specfile(content)
        new_p.build_package()
        if new_p.build_ok:
            print "Build successfull, package locations:"
            print new_p.long_package_name
            print new_p.src_package_name
            success = True
        else:
            print "Something went wrong, please check tempdir %s" % (self.tempdir)
            success = False
        return success

def main():
    my_parser = my_opt_parser()
    my_parser.parse()
    print my_parser.get_compile_options()
    my_builder = fftw_builder(my_parser)
    my_builder.build_it()

if __name__ == "__main__":
    main()