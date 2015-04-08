# arch!/usr/bin/python-init -Otu
#
# Copyright (c) 2007-2008,2014 Andreas Lang-Nevyjel, lang-nevyjel@init.at
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

import argparse
import commands
import compile_tools
import cpu_database
import logging_tools
import optparse
import os
import rpm_build_tools
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HPL_VERSION_FILE = "/opt/cluster/share/hpl_versions"


class my_opt_parser(optparse.OptionParser):
    def __init__(self):
        optparse.OptionParser.__init__(self)
        # check for 64-bit Machine
        self.mach_arch = os.uname()[4]
        if self.mach_arch in ["x86_64", "ia64"]:
            is_64_bit = True
        else:
            is_64_bit = False
        self._read_hpl_versions()
        target_dir = "/opt/cluster/hpl/"
        self.set_defaults(
            fcompiler="GNU",
            hpl_version=self.highest_version,
            use_64_bit=is_64_bit,
            target_dir=target_dir,
            include_log=False,
            fcompiler_path="NOT_SET",
            mpi_path="NOT SET",
            goto_lib="NOT SET",
            ignore_libgoto=False,
            ignore_mpi=False,
            ignore_compiler=False,
            extra_settings="",
            verbose=False,
            arch=self.mach_arch
        )
        fc_choices = sorted(["GNU",
                             "INTEL",
                             "PATHSCALE"])
        self.cpu_id = cpu_database.get_cpuid()
        self.add_option(
            "-c",
            type="choice",
            dest="fcompiler",
            help="Set Compiler type, options are %s" % (", ".join(fc_choices)),
            action="store",
            choices=fc_choices
        )
        self.add_option(
            "--fpath",
            type="string",
            dest="fcompiler_path",
            help="Compiler Base Path, for instance /opt/intel/compiler-9.1"
        )
        self.add_option(
            "--mpi-path",
            type="string",
            dest="mpi_path",
            help="MPI Base Path, for instance /opt/libs/openmpi-1.2.2-INTEL-9.1.045-32/"
        )
        self.add_option(
            "--goto-lib",
            type="string",
            dest="goto_lib",
            help="libgoto to use, for instance /opt/libs/libgoto/libgoto-0_64k2M0_6.14.8.10-32-r1.13.a [%default]",
            default=""
        )
        self.add_option(
            "--mkl-lib",
            type="string",
            dest="mkl_lib",
            help="directory of mkl use, for instance /opt/intel/Compiler/11.1/046/mkl/ [%default]",
            default=""
        )
        self.add_option(
            "-H",
            type="choice",
            dest="hpl_version",
            help="Choose HPL Version, possible values are %s" % (", ".join(self.version_dict.keys())),
            action="store",
            choices=self.version_dict.keys()
        )
        self.add_option(
            "--fflags",
            type="string",
            dest="compiler_fflags",
            help="Set flags for Fortran compiler",
            default="-fomit-frame-pointer -O3 -funroll-loops -W -Wall"
        )
        self.add_option(
            "--cflags",
            type="string",
            dest="compiler_cflags",
            help="Set flags for C compiler",
            default="-fomit-frame-pointer -O3 -funroll-loops -W -Wall"
        )
        self.add_option(
            "-d",
            type="string",
            dest="target_dir",
            help="Sets target directory, default is %s" % (target_dir),
            action="store"
        )
        self.add_option(
            "--arch",
            type="str",
            dest="arch",
            help="Set package architecture"
        )
        self.add_option(
            "--log",
            dest="include_log",
            help="Include log of make-command in README",
            action="store_true"
        )
        self.add_option("--ignore-goto", dest="ignore_libgoto", help="Ignore Version of libgoto", action="store_true")
        self.add_option("--ignore-mpi", dest="ignore_mpi", help="Ignore Version of libmpi", action="store_true")
        self.add_option("--ignore-compiler", dest="ignore_compiler", help="Ignore Version of compiler", action="store_true")
        self.add_option("--use-mkl", dest="use_mkl", action="store_true", help="use intel MKL not libgoto [%default]", default=False)
        self.add_option("-v", dest="verbose", help="Set verbose level", action="store_true")
        if is_64_bit:
            # add option for 32-bit goto if machine is NOT 32 bit
            self.add_option("--32", dest="use_64_bit", help="Set 32-Bit HPL", action="store_false")

    def parse(self):
        options, args = self.parse_args()
        if args:
            print "Additional arguments found, exiting"
            sys.exit(0)
        self.options = options
        self._check_compiler_settings()
        self.package_name = "hpl-%s-%s-%s-%s-%s-%s-%s%s" % (self.options.hpl_version,
                                                            self.options.fcompiler,
                                                            self.small_version,
                                                            self.mpi_version,
                                                            self.blas_version,
                                                            self.cpu_id,
                                                            self.options.use_64_bit and "64" or "32",
                                                            self.options.extra_settings and "-%s" % (self.options.extra_settings) or "")
        self.hpl_dir = "%s/%s" % (self.options.target_dir,
                                  self.package_name)

    def _check_compiler_settings(self):
        self.add_path_dict = {}
        if self.options.fcompiler == "GNU":
            self.compiler_dict = {
                "CC": "gcc",
                "CPP": "cpp",
                "F77": "gfortran",
                "FC": "gfortran"
            }
            stat, out = commands.getstatusoutput("gcc --version")
            if stat:
                raise ValueError("Cannot get Version from gcc (%d): %s" % (stat, out))
            self.small_version = out.split("\n")[0].split()[2]
            self.compiler_version_dict = {"GCC": out}
        elif self.options.fcompiler == "INTEL":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = compile_tools.get_add_paths_for_intel(self.options.fcompiler_path)
                self.compiler_dict = {
                    "CC": "icc",
                    "CXX": "icpc",
                    "F77": "ifort"
                }
                ifort_out_lines, small_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path, "ifort")
                if not small_version:
                    sys.exit(-1)
                self.small_version = small_version
                ifort_out = "\n".join(ifort_out_lines)
                self.compiler_version_dict = {"ifort": ifort_out}
                icc_out_lines, _short_icc_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path, "icc")
                icc_out = "\n".join(icc_out_lines)
                self.compiler_version_dict = {
                    "ifort": ifort_out,
                    "icc": icc_out
                }
            else:
                raise IOError(
                    "Compiler base path '{}' for compiler setting {} is not a directory".format(
                        self.options.fcompiler_path,
                        self.options.fcompiler
                    )
                )
        elif self.options.fcompiler == "PATHSCALE":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = {
                    "LD_LIBRARY_PATH": ["%s/lib" % (self.options.fcompiler_path)],
                    "PATH": ["%s/bin" % (self.options.fcompiler_path)]
                }
                self.compiler_dict = {
                    "CC": "pathcc",
                    "CXX": "pathCC",
                    "F77": "pathf95"
                }
                stat, pathf95_out = commands.getstatusoutput("%s/bin/pathf95 -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError("Cannot get Version from pathf95 (%d): %s" % (stat, pathf95_out))
                self.small_version = pathf95_out.split("\n")[0]
                self.compiler_version_dict = {"pathf95": pathf95_out}
                stat, pathcc_out = commands.getstatusoutput("%s/bin/pathcc -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError("Cannot get Version from pathcc (%d): %s" % (stat, pathcc_out))
                self.compiler_version_dict = {
                    "pathf95": pathf95_out,
                    "pathcc": pathcc_out
                }
            else:
                raise IOError(
                    "Compiler base path '{}' for compiler setting {} is not a directory".format(
                        self.options.fcompiler_path,
                        self.options.fcompiler
                    )
                )
        else:
            raise ValueError("Compiler settings %s unknown" % (self.options.fcompiler))
        compiler_sig = "%s-%s" % (self.options.fcompiler, self.small_version)
        if not os.path.isdir(self.options.mpi_path):
            raise IOError("MPI base path '%s' is not a directory" % (self.options.mpi_path))
        elif not self.options.mpi_path.count(compiler_sig):
            raise ValueError("MPI base path '%s' has the wrong Compiler signature %s" % (self.options.mpi_path, compiler_sig))
        else:
            # MPI is OK
            p_split = os.path.split(self.options.mpi_path)
            if not p_split[1]:
                p_split = os.path.split(p_split[0])
            self.mpi_version = p_split[1][0: p_split[1].index(compiler_sig) - 1]
        if self.options.use_mkl:
            if not os.path.isdir(self.options.mkl_lib):
                raise IOError("MKL Directorypath '%s' is not a directory" % (self.options.mkl_lib))
            else:
                self.blas_version = "mkl"
        else:
            if not os.path.isfile(self.options.goto_lib):
                raise IOError("Goto Library '%s' is not a file" % (self.options.goto_lib))
            else:
                if not (self.options.goto_lib.endswith(".a") or self.options.goto_lib.endswith(".so")):
                    raise ValueError("Goto Library '%s' must end with .a or .so" % (self.options.goto_lib))
                elif not self.options.goto_lib.count(self.cpu_id) and not self.options.ignore_libgoto:
                    raise ValueError("Goto Library '%s' has wrong cpu_id (should have %s)" % (self.options.goto_lib, self.cpu_id))
                else:
                    self.blas_version = ".".join(self.options.goto_lib.split("-")[-1].split(".")[0:2])

    def _read_hpl_versions(self):
        if os.path.isfile(HPL_VERSION_FILE):
            version_lines = [line.strip().split() for line in file(HPL_VERSION_FILE, "r").read().split("\n") if line.strip()]
            self.version_dict = dict([(key, value) for key, value in version_lines])
            vers_dict = dict([(tuple([part.isdigit() and int(part) or part for part in key.split(".")]), key) for key in self.version_dict.keys()])
            vers_keys = sorted(vers_dict.keys())
            self.highest_version = vers_dict[vers_keys[-1]]
        else:
            raise IOError("No %s found" % (HPL_VERSION_FILE))

    def get_compile_options(self):
        ret_lines = [" - build_date is %s" % (time.ctime()),
                     " - hpl Version is %s, cpuid is %s" % (self.options.hpl_version,
                                                            self.cpu_id),
                     " - Compiler is %s, Compiler Base path is %s" % (self.options.fcompiler,
                                                                      self.options.fcompiler_path),
                     " - MPI base path is %s" % (self.options.mpi_path)]
        if self.options.use_mkl:
            ret_lines.append(" - using mkl")
        else:
            ret_lines.append(" - libgoto is %s" % (self.options.goto_lib))
        ret_lines.extend(
            [
                " - small_verison is {}".format(self.small_version),
                " - source package is {}, target directory is {}".format(
                    self.version_dict[self.options.hpl_version],
                    self.hpl_dir
                ),
                " - package name choosen is {}".format(self.package_name),
                "compiler settings: {}".format(", ".join(["%s=%s" % (key, value) for key, value in self.compiler_dict.iteritems()])),
                "add_path_dict    : {}".format(", ".join(["%s=%s:$%s" % (key, ":".join(value), key) for key, value in self.add_path_dict.iteritems()])),
                "version info:"
            ] + [
                "{}:\n{}".format(
                    key,
                    "\n".join(
                        [
                            "    {}".format(line.strip()) for line in value.split("\n")
                        ]
                    )
                ) for key, value in self.compiler_version_dict.iteritems()
            ]
        )
        return "\n".join(ret_lines)


class hpl_builder(object):
    def __init__(self, parser):
        self.parser = parser
        self.cpu_arch = "cpu"

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
        self.tempdir = tempfile.mkdtemp("_hpl")
        self.tempdir_2 = ""

    def _remove_tempdir(self):
        print "Removing temporary directories"
        shutil.rmtree(self.tempdir)
        try:
            os.rmdir(self.tempdir)
        except:
            pass
        if self.tempdir_2:
            shutil.rmtree(self.tempdir_2)
            try:
                os.rmdir(self.tempdir_2)
            except:
                pass

    def _untar_source(self):
        tar_source = self.parser.version_dict[self.parser.options.hpl_version]
        if not os.path.isfile(tar_source):
            print "Cannot find Hpl source %s" % (tar_source)
            success = False
        else:
            print "Extracting tarfile %s ..." % (tar_source),
            tar_file = tarfile.open(tar_source, "r")
            tar_file.extractall(self.tempdir)
            tar_file.close()
            print "done"
            success = True
        return success

    def _generate_makefile(self):
        mfile = os.path.join(
            self._hpl_dir,
            "Make.{}".format(self.cpu_arch)
        )
        make_list = [
            ("SHELL", "/bin/sh"),
            ("CD", "cd"),
            ("CP", "cp"),
            ("LN_S", "ln -s"),
            ("MKDIR", "mkdir"),
            ("RM", "/bin/rm -f"),
            ("TOUCH", "touch"),
            ("ARCH", self.cpu_arch),
            ("TOPdir", self._hpl_dir),
            ("INCdir", "$(TOPdir)/include"),
            ("BINdir", "$(TOPdir)/bin/$(ARCH)"),
            ("LIBdir", "$(TOPdir)/lib/$(ARCH)"),
            ("HPLlib", "$(LIBdir)/libhpl.a "),
            ("MPdir", self.parser.options.mpi_path),
            ("MPinc", "-I$(MPdir)/include"),
            ("MPlib", "$(MPdir)/lib/libmpi.so")
        ]
        if self.parser.options.use_mkl:
            make_list.extend(
                [
                    ("LAdir", "%s/lib/intel64" % (self.parser.options.mkl_lib)),
                    ("LAinc", ""),
                    ("LAlib", "-L$(LAdir) $(LAdir)/libmkl_intel_lp64.a $(LAdir)/libmkl_sequential.a $(LAdir)/libmkl_core.a")
                ]
            )
        else:
            make_list.extend(
                [
                    ("LAdir", os.path.dirname(self.parser.options.goto_lib)),
                    ("LAinc", ""),
                    ("LAlib", self.parser.options.goto_lib)
                ]
            )
        make_list.extend(
            [
                ("F2CDEFS", ""),
                ("HPL_INCLUDES", "-I$(INCdir) -I$(INCdir)/$(ARCH) $(LAinc) $(MPinc)"),
                ("HPL_LIBS", "$(HPLlib) $(LAlib) $(MPlib)"),
                ("HPL_DEFS", "$(F2CDEFS) $(HPL_OPTS) $(HPL_INCLUDES)"),
                ("CC", self.parser.compiler_dict["CC"]),
                ("CCNOOPT", "$(HPL_DEFS) %s" % (self.parser.options.compiler_cflags)),
                ("CCFLAGS", "$(HPL_DEFS) %s" % (self.parser.options.compiler_cflags)),
                ("LINKER", self.parser.compiler_dict["CC"]),
                ("LINKFLAGS", "$(CCFLAGS)"),
                ("ARCHIVER", "ar"),
                ("ARFLAGS", "r"),
                ("RANLIB", "echo")
            ]
        )
        file(mfile, "w").write("\n".join(["%-12s = %s" % (key, value) for key, value in make_list] + [""]))

    def _compile_it(self):
        act_dir = os.getcwd()
        self._hpl_dir_name = os.listdir(self.tempdir)[0]
        self._hpl_dir = os.path.join(self.tempdir, self._hpl_dir_name)
        os.chdir(self._hpl_dir)
        print "Modifying environment"
        for env_name, env_value in self.parser.compiler_dict.iteritems():
            os.environ[env_name] = env_value
        for path_name, path_add_value in self.parser.add_path_dict.iteritems():
            os.environ[path_name] = "%s:%s" % (":".join(path_add_value), os.environ.get(path_name, ""))
        self._generate_makefile()
        self.time_dict, self.log_dict = ({}, {})
        success = True
        for command, time_name in [("make arch=%s" % (self.cpu_arch), "make")]:
            self.time_dict[time_name] = {"start": time.time()}
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
                        if type(new_lines) == list:
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
        self.tempdir_2 = tempfile.mkdtemp("_hpl")
        info_name = "README.%s" % (self.parser.package_name)
        sep_str = "-" * 50
        readme_lines = [sep_str] + \
            self.parser.get_compile_options().split("\n") + \
            [
                "Compile times: {}".format(
                    ", ".join(
                        [
                            "{}: {}".format(
                                key,
                                logging_tools.get_diff_time_str(self.time_dict[key]["diff"])
                            ) for key in self.time_dict.keys()
                        ]
                    )
                ),
                sep_str, ""
            ]
        if self.parser.options.include_log:
            readme_lines.extend(
                [
                    "Compile logs:"
                ] + sum(
                    [
                        self.log_dict[key].split("\n") + [sep_str] for key in self.log_dict.keys()
                    ],
                    []
                )
            )
        file("%s/%s" % (self.tempdir_2, info_name), "w").write("\n".join(readme_lines))
        package_name, package_version, package_release = (self.parser.package_name,
                                                          self.parser.options.hpl_version,
                                                          "1")
        hpl_base_dir = os.path.join(
            self._hpl_dir,
            "bin",
            self.cpu_arch
        )
        xhpl_file_name = "%s/xhpl" % (hpl_base_dir)
        if not os.path.isfile(xhpl_file_name):
            print "Cannot find %s" % (xhpl_file_name)
            success = False
        else:
            file("%s/xhpl" % (self.tempdir_2), "wb").write(file(xhpl_file_name, "rb").read())
            file("%s/Make.%s" % (self.tempdir_2, self.parser.package_name), "wb").write(
                file(
                    os.path.join(self._hpl_dir, "Make.{}".format(self.cpu_arch)),
                    "rb"
                ).read()
            )
            file("%s/HPL.dat" % (self.tempdir_2), "wb").write(file("%s/HPL.dat" % (hpl_base_dir), "rb").read())
            os.chmod("%s/xhpl" % (self.tempdir_2), 0775)
            dummy_args = argparse.Namespace(
                name=package_name,
                version=package_version,
                release=package_release,
                package_group="Tools/Benchmark",
                arch=self.parser.options.arch,
                description="HPL",
                summary="HPL",
            )

            new_p = rpm_build_tools.build_package(dummy_args)
            new_p["inst_options"] = " -p "
            content = rpm_build_tools.file_content_list(["%s:%s" % (self.tempdir_2, self.parser.hpl_dir)])
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
    my_builder = hpl_builder(my_parser)
    my_builder.build_it()

if __name__ == "__main__":
    main()
