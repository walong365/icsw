#!/usr/bin/python3-init -Otu
#
# Copyright (c) 2007,2008,2009,2012 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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
import os
import os.path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import codecs

from initat.tools import cpu_database, logging_tools, rpm_build_tools, compile_tools

LIBGOTO_VERSION_FILE = "/opt/cluster/share/source-versions/libgoto_versions"


class my_opt_parser(argparse.ArgumentParser):
    class check_nr_of_threads(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None, required=False, help=None, metavar=None):
            super(my_opt_parser.check_nr_of_threads, self).__init__(option_strings=option_strings, dest=dest, nargs=nargs, const=const, default=default, type=type, choices=choices, required=required, help=help, metavar=metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, values)

    def __init__(self):
        argparse.ArgumentParser.__init__(self, description="compile BLAS implementation")
        # check for 64-bit Machine
        self.mach_arch = os.uname()[4]
        if self.mach_arch in ["x86_64", "ia64"]:
            is_64_bit = True
        else:
            is_64_bit = False
        self._read_libgoto_versions()
        target_dir = "/opt/libs/libgoto"
        cc_choices = sorted(
            [
                "GNU",
                "INTEL",
                "PATHSCALE"
            ]
        )
        fc_choices = sorted(
            [
                "G77",
                "GFORTRAN",
                "G95",
                "INTEL",
                "PGI",
                "PATHSCALE",
                "IBM",
                "COMPAQ",
                "SUN",
                "F2C"
            ]
        )
        self.cpu_id = cpu_database.get_cpuid()
        self.add_argument(
            "-f", type=str, dest="fcompiler", help="Set Fortran Compiler, options are %s [%%(default)s]" % (", ".join(fc_choices)),
            action="store", choices=fc_choices, default="GFORTRAN")
        self.add_argument(
            "-c", type=str, dest="ccompiler", help="Set C Compiler, options are %s [%%(default)s]" % (", ".join(cc_choices)), action="store",
            choices=cc_choices, default="GNU")
        self.add_argument("-a", type=str, dest="archiver", help="Set archiver [%(default)s]", default="ar")
        self.add_argument("-l", type=str, dest="linker", help="Set linker [%(default)s]", default="ld")
        self.add_argument(
            "--fpath", type=str, dest="fcompiler_path", help="Compiler Base Path, for instance /opt/intel/compiler-9.1 [%(default)s]",
            default="NOT_SET")
        self.add_argument("--cflags", type=str, dest="compiler_flags", help="Set flags for COMPILER [%(default)s]", default="")
        self.add_argument("--fflags", type=str, dest="compiler_f77_flags", help="Set flags for COMPILER_F77 [%(default)s]", default="")
        self.add_argument("--nosmp", dest="smp", help="Disable SMP option [%(default)s]", action="store_false", default=True)
        self.add_argument("--maxthreads", type=int, dest="max_threads", action=my_opt_parser.check_nr_of_threads, help="Set number of threads supported [%(default)d]", default=16)
        self.add_argument("--arch", type=str, dest="arch", help="Set package architecture [%(default)s]", default="")
        self.add_argument(
            "-g", type=str, dest="goto_version",
            help="Choose LibGoto Version, possible values are %s [%%(default)s]" % (", ".join(list(self.version_dict.keys()))), action="store",
            choices=list(self.version_dict.keys()),
            default=self.highest_version)
        self.add_argument("-d", type=str, dest="target_dir", help="Sets target directory [%(default)s]", action="store", default=target_dir)
        self.add_argument("--log", dest="include_log", help="Include log of make-command in README [%(default)s]", action="store_true", default=False)
        self.add_argument("-v", dest="verbose", help="Set verbose level [%(default)s]", action="store_true", default=False)
        self.add_argument("--release", dest="release", type=str, help="Set release [%(default)s]", default="1")
        if is_64_bit:
            # add option for 32-bit goto if machine is NOT 32 bit
            self.add_argument("--32", dest="use_64_bit", help="Set 32-Bit Goto [%(default)s]", action="store_false", default=is_64_bit)
            self.add_argument("--if64", dest="use_64_bit_interface", help="Use INTERFACE64 in Makefile [%(default)s]", action="store_true", default=False)

    def parse(self):
        options = self.parse_args()
        self.options = options
        self._check_compiler_settings()

    def _check_max_threads(self, option, opt_str, value, parser):
        if value < 1 or value > 128:
            raise optparse.OptionValueError("%s for %s is out of range [1, 128]" % (value, option))
        else:
            setattr(self.values, option.dest, value)

    def _read_libgoto_versions(self):
        if os.path.isfile(LIBGOTO_VERSION_FILE):
            version_lines = [line.strip().split() for line in open(LIBGOTO_VERSION_FILE, "r").read().split("\n") if line.strip()]
            self.version_dict = dict([(key, value) for key, value in version_lines])
            vers_dict = dict([(tuple([part.isdigit() and int(part)+1 or part for part in key.split(".")]), key) for key in list(self.version_dict.keys())])
            vers_keys = sorted(vers_dict.keys())
            self.highest_version = vers_dict[vers_keys[-1]]
        else:
            raise IOError("No %s found" % (LIBGOTO_VERSION_FILE))

    def get_compile_options(self):
        return "\n".join(
            [
                " - build_date is %s" % (time.ctime()),
                " - libgoto Version is %s, cpuid is %s" % (
                    self.options.goto_version,
                    self.cpu_id
                ),
                " - C Compiler is %s, Fortran Compiler is %s" % (
                    self.options.ccompiler,
                    self.options.fcompiler
                ),
                " - short_verison is %s" % (self.short_version),
                " - source package is %s, target directory is %s" % (
                    self.version_dict[self.options.goto_version],
                    self.options.target_dir
                ),
                " - SMP flag is %s, 64 Bit is %s, 64 Bit Interface is %s, max_threads is %d" % (
                    self.options.smp and "True" or "False",
                    self.options.use_64_bit and "enabled" or "disabled",
                    self.options.use_64_bit_interface and "enabled" or "disabled",
                    self.options.max_threads
                ),
                "version info:",
                "compiler settings: %s" % ", ".join(["%s=%s" % (key, value) for key, value in self.compiler_dict.items()]),
                "add_path_dict    : %s" % ", ".join(["%s=%s:$%s" % (key, ":".join(value), key) for key, value in self.add_path_dict.items()])
            ] + [
                "%s:\n%s" % (key, "\n".join(["    %s" % (line.strip()) for line in value.split("\n")])) for key, value in
                self.compiler_version_dict.items()
            ]
        )

    def _check_compiler_settings(self):
        self.add_path_dict = {}
        if self.options.fcompiler in ["GNU", "GFORTRAN", "G77"]:
            self.compiler_dict = {"CC": "gcc",
                                  "CXX": "g++",
                                  "F77": "gfortran",
                                  "FC": "gfortran"}
            #stat, out = subprocess.getstatusoutput("gcc --version")
            stat, out = subprocess.getstatusoutput("gcc -v")
            if stat:
                raise ValueError("Cannot get Version from gcc (%d): %s" % (stat, out))
            #self.short_version = out.split("\n")[0].split()[2]
            self.short_version = out.split("\n")[-1].split()[2]
            self.compiler_version_dict = {"GCC": out}
        elif self.options.fcompiler == "INTEL":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = compile_tools.get_add_paths_for_intel(self.options.fcompiler_path)
                self.compiler_dict = {"CC": "icc",
                                      "CXX": "icpc",
                                      "F77": "ifort"}
                ifort_out_lines, short_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path, "ifort")
                if not short_version:
                    sys.exit(-1)
                self.short_version = short_version
                ifort_out = "\n".join(ifort_out_lines)
                self.compiler_version_dict = {"ifort": ifort_out}
                icc_out_lines, short_icc_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path, "icc")
                icc_out = "\n".join(icc_out_lines)
                self.compiler_version_dict = {"ifort": ifort_out,
                                              "icc": icc_out}
            else:
                raise IOError(
                    "Compiler base path '%s' for compiler setting %s is not a directory" % (
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
                stat, pathf95_out = subprocess.getstatusoutput("%s/bin/pathf95 -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError("Cannot get Version from pathf95 (%d): %s" % (stat, pathf95_out))
                self.short_version = pathf95_out.split("\n")[0]
                self.compiler_version_dict = {"pathf95": pathf95_out}
                stat, pathcc_out = subprocess.getstatusoutput("%s/bin/pathcc -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError("Cannot get Version from pathcc (%d): %s" % (stat, pathcc_out))
                self.compiler_version_dict = {
                    "pathf95": pathf95_out,
                    "pathcc": pathcc_out
                }
            else:
                raise IOError(
                    "Compiler base path '%s' for compiler setting %s is not a directory" % (
                        self.options.fcompiler_path,
                        self.options.fcompiler
                    )
                )
        else:
            raise ValueError("Compiler settings %s unknown" % (self.options.fcompiler))


class build_task(object):
    def __init__(self, **args):
        self.info = args["info"]
        self.work_dir = args.get("directory", os.getcwd())
        self.command = args["command"]
        self.verbose = args.get("verbose", False)
        self.out_lines = []

    def build(self):
        act_dir = os.getcwd()
        self.start_time = time.time()
        os.chdir(self.work_dir)
        print("Calling command %s (directory: %s)" % (self.command, self.work_dir))
        sp_obj = subprocess.Popen(self.command.split(), 0, None, None, subprocess.PIPE, subprocess.STDOUT)
        out_lines = []
        while True:
            stat = sp_obj.poll()
            while True:
                try:
                    new_lines = next(sp_obj.stdout)
                except StopIteration:
                    break
                else:
                    if self.verbose:
                        print(new_lines.decode(), end=' ')
                    if type(new_lines) is list:
                        self.out_lines.extend(new_lines)
                    else:
                        self.out_lines.append(new_lines)
            if stat is not None:
                break
        self.end_time = time.time()
        self.state = stat
        os.chdir(act_dir)
        self.run_time = self.end_time - self.start_time


class goto_builder(object):
    def __init__(self, parser):
        self.parser = parser
        self.dirname = ""

    def do_it(self):
        self.compile_ok = False
        self._init_tempdir()
        if self._untar_source():
            if self._build_makefile_rule():
                if self._compile_it():
                    if self.package_it():
                        self.compile_ok = True
                        self._remove_tempdir()
        if not self.compile_ok:
            print("Not removing temporary directory %s" % (self.tempdir))

    def _init_tempdir(self):
        self.tempdir = tempfile.mkdtemp("_goto")

    def _remove_tempdir(self):
        print("Removing temporary directories")
        shutil.rmtree(self.tempdir)
        try:
            os.rmdir(self.tempdir)
        except:
            pass

    def _untar_source(self):
        tar_source = self.parser.version_dict[self.parser.options.goto_version]
        if not os.path.isfile(tar_source):
            print("Cannot find libgoto source %s" % (tar_source))
            success = False
        else:
            print("Extracting tarfile %s ..." % (tar_source), end=' ')
            tar_file = tarfile.open(tar_source, "r")
            self.dirname = os.path.commonprefix(tar_file.getnames())
            tar_file.extractall(self.tempdir)
            tar_file.close()
            print("done")
            success = True
        return success

    def _build_makefile_rule(self):
        self.orig_rulefile_name = "{}/{}/Makefile.rule".format(self.tempdir, self.dirname)
        if not os.path.isfile(self.orig_rulefile_name):
            print("Cannot find %s" % (self.orig_rulefile_name))
            success = False
        else:
            print("Modifying Makefile.rule")
            rule_lines = [line for line in open(self.orig_rulefile_name, "r").read().split("\n") if line.rstrip() and not line.lstrip().startswith("#")]
            parser_options = self.parser.options
            pre_new_rules = [
                ("C_COMPILER", parser_options.ccompiler),
                ("F_COMPILER", parser_options.fcompiler),
                ("BINARY64", parser_options.use_64_bit and "1" or ""),
                ("SMP", parser_options.smp and "1" or ""),
                ("MAX_THREADS", "%d" % (parser_options.max_threads)),
                ("INTERFACE64", parser_options.use_64_bit_interface and "1" or ""),
                ("AR", parser_options.archiver),
                ("LD", parser_options.linker)
            ]
            post_new_rules = [
                ("CCOMMON_OPT", parser_options.compiler_flags),
                ("FCOMMON_OPT", parser_options.compiler_f77_flags)
            ]
            new_keys = [name for name, value in pre_new_rules]
            rule_lines = [line for line in rule_lines if line.split()[0] not in new_keys]
            rule_lines = [
                "%-12s = %s" % (name, value) for name, value in pre_new_rules
            ] + rule_lines + [
                "%-12s += %s" % (name, value) for name, value in post_new_rules
            ] + [""]
            codecs.open(self.orig_rulefile_name, mode="w", encoding='utf-8').write("\n".join(rule_lines))
            success = True
        return success

    def _compile_it(self):
        num_cores = cpu_database.CPUId(parse=True).num_cores
        self.time_dict, self.log_dict = ({}, {})
        success = True
        act_dir = os.getcwd()
        for path_name, path_add_value in self.parser.add_path_dict.items():
            os.environ[path_name] = "%s:%s" % (":".join(path_add_value), os.environ.get(path_name, ""))
        for command, act_dir, time_name in [
            ("make -j {}".format(num_cores), "{}/{}".format(self.tempdir, self.dirname), "make"),
            ("make so", "{}/{}/exports".format(self.tempdir, self.dirname), "make so"),
            ("make all", "{}/{}/test".format(self.tempdir, self.dirname), "make check"),
        ]:
            b_task = build_task(
                info=time_name,
                directory=act_dir,
                command=command,
                verbose=self.parser.options.verbose
            )
            b_task.build()
            self.time_dict[time_name] = b_task.run_time
            self.log_dict[time_name] = "".join(map(bytes.decode, b_task.out_lines))
            if b_task.state:
                print("Something went wrong (%d):" % (b_task.state))
                if not self.parser.options.verbose:
                    print("".join(map(bytes.decode, b_task.out_lines)))
                success = False
            else:
                print("done, took %s" % (logging_tools.get_diff_time_str(self.time_dict[time_name])))
        os.chdir(act_dir)
        if success:
            libgoto_static_file_name = "/static_not_found"
            libgoto_dynamic_file_name = "/dynamic_not_found"
            for ent in os.listdir("{}/{}".format(self.tempdir, self.dirname)):
                fpath = "{}/{}/{}".format(self.tempdir, self.dirname, ent)
                if ent.endswith(".a") and os.path.isfile(fpath) and not os.path.islink(fpath):
                    libgoto_static_file_name = fpath
                if ent.endswith(".so") and os.path.isfile(fpath) and not os.path.islink(fpath):
                    libgoto_dynamic_file_name = fpath
                fpath = ""
            if os.path.isfile(libgoto_static_file_name) and os.path.isfile(libgoto_dynamic_file_name):
                success = True
            else:
                print("Cannot find library %s" % (libgoto_static_file_name))
                success = False
        return success

    def package_it(self):
        print("Packaging ...")
        width = self.parser.options.use_64_bit and "64" or "32"
        libgoto_info_str = "%s-%s-%s-%s%s" % (
            self.parser.cpu_id,
            self.parser.options.fcompiler,
            self.parser.short_version,
            width,
            self.parser.options.smp and "p" or ""
        )
        libgoto_vers_str = "%s-r%s" % (
            libgoto_info_str,
            self.parser.options.goto_version
        )
        static_library_name, dynamic_library_name = (
            "libgoto-%s.a" % (libgoto_vers_str),
            "libgoto-%s.so" % (libgoto_vers_str)
        )
        info_name = "README.libgoto-%s" % (libgoto_vers_str)
        sep_str = "-" * 50
        readme_lines = [
            sep_str
        ] + self.parser.get_compile_options().split("\n") + [
            "Compile times: %s" % (
                ", ".join(
                    [
                        "%s: %s" % (key, logging_tools.get_diff_time_str(self.time_dict[key])) for key in list(self.time_dict.keys())
                    ]
                )
            ),
            sep_str,
            ""
        ]
        if self.parser.options.include_log:
            readme_lines.extend(
                [
                    "Compile logs:"
                ] + sum([["%s:" % (key)] + self.log_dict[key].split("\n") + [sep_str] for key in list(self.log_dict.keys())], []))

        libgoto_static_file_name, libgoto_dynamic_file_name = ("/static_not_found", "/dynamic_not_found")
        codecs.open("{}/info".format(self.tempdir), "w", encoding='utf-8').write("\n".join(readme_lines))
        for ent in os.listdir("{}/{}".format(self.tempdir, self.dirname)):
            fpath = "{}/{}/{}".format(self.tempdir, self.dirname, ent)
            if ent.endswith(".a") and (os.path.isfile(fpath) and not os.path.islink(fpath)):
                libgoto_static_file_name = fpath
            if ent.endswith(".so") and (os.path.isfile(fpath) and not os.path.islink(fpath)):
                libgoto_dynamic_file_name = fpath
            fpath = ""
        package_name, package_version, package_release = (
            "libgoto-%s" % (libgoto_info_str),
            self.parser.options.goto_version,
            self.parser.options.release
        )
        # copy libgoto.a
        codecs.open("{}.static".format(libgoto_static_file_name), "wb").write(open(libgoto_static_file_name, "rb").read())
        dummy_args = argparse.Namespace(
            name=package_name,
            version=package_version,
            release=package_release,
            package_group="Libraries/Math",
            description="BLAS",
            summary="BLAS Package",
        )
        new_p = rpm_build_tools.build_package(dummy_args)
        if self.parser.options.arch:
            new_p["arch"] = self.parser.options.arch
        new_p["inst_options"] = " -p "
        content = rpm_build_tools.file_content_list(
            [
                "%s.static:%s/%s" % (
                    libgoto_static_file_name,
                    self.parser.options.target_dir,
                    static_library_name
                ),
                "%s:%s/%s" % (
                    libgoto_dynamic_file_name,
                    self.parser.options.target_dir,
                    dynamic_library_name
                ),
                "%s/info:%s/%s" % (
                    self.tempdir,
                    self.parser.options.target_dir,
                    info_name
                ),
                "%s:%s/Makefile.rule.%s" % (
                    self.orig_rulefile_name,
                    self.parser.options.target_dir,
                    libgoto_vers_str
                )
            ]
        )
        new_p.create_tgz_file(content)
        new_p.write_specfile(content)
        new_p.build_package()
        if new_p.build_ok:
            print("Build successfull, package locations:")
            print(new_p.long_package_name)
            print(new_p.src_package_name)
            success = True
        else:
            print("Something went wrong, please check tempdir %s" % (self.tempdir))
            success = False
        return success


def main():
    my_parser = my_opt_parser()
    my_parser.parse()
    print(my_parser.get_compile_options())
    my_builder = goto_builder(my_parser)
    my_builder.do_it()


if __name__ == "__main__":
    main()
