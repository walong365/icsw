#!/usr/bin/python-init
# -*- coding: utf-8 -*-

"""
Inspect python files passed to this script for signs of taking commandline
arguments. Uses help2man to create a manpage from the --help/-h output.
"""

import argparse
import re
import os
import sys
import subprocess
from subprocess import CalledProcessError
from symtable import symtable
from gzip import GzipFile

IMPORT_SYMBOLS = ("argparse", "ArgumentParser", "optparse")


def read_symboltable(path):
    with open(path, "r") as f:
        try:
            return symtable(f.read(), path, "exec")
        except SyntaxError:
            pass


def valid_file(path):
    """ Check if path is a python file"""
    executable = os.access(path, os.X_OK) and path.endswith(".py")

    if executable and os.path.isfile(path):
        with open(path, "r") as f:
            first_line = f.readline()
        return "python" in first_line
    else:
        return False


def help2man(path):
    """ Call help to man and try different arguments for success """
    args = [
        [],
        ["--version-string", "NO_VERSION_INFO"],
        ["--help-option", "--h"],
        ["--help-option", "--h", "--version-string", "NO_VERSION_INFO"],
    ]
    man = None

    for arg in args:
        try:
            man = subprocess.check_output(["help2man", "-N"] + arg + [path],
                                          stderr=subprocess.STDOUT)
        except CalledProcessError:
            pass
        else:
            break
    return man


def write_manpage(filename, content, file_creator=open):
    if os.path.exists(filename):
        print "Not writing {}: File exists!".format(filename)
    else:
        with file_creator(filename, "w") as f:
            f.write(content)


def main():
    # Check if help2man is installed
    try:
        subprocess.check_output(["help2man", "--help"], stderr=subprocess.STDOUT)
    except OSError:
        print "Install 'help2man' to use this script!"
        sys.exit(1)

    symbol_tables = []
    files_to_check = []

    description = \
    """
Try to create man pages from optparse/argparse output.
The script checks if argparse/optarse is an imported symbol. If it is
then the script is executed with --help/-h and the output rendered into
a man page.
    """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("paths", nargs="+", type=str, help="Directories or files to check")
    parser.add_argument("--quiet", action="store_true", help="Be quiet")
    parser.add_argument("--nogz", action="store_const", default=(GzipFile, ".gz"),
                        const=(open, ""), help="Don't gzip the resulting files")
    parser.add_argument("--list", action="store_true", help="Just output the found files")
    args = parser.parse_args()

    def output(message):
        if args.quiet:
            return
        else:
            print message

    output("[+] Scanning files and generating symbol tables")
    for path in args.paths:
        if valid_file(path):
            symbol_tables.append(read_symboltable(path))
        elif os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    fullpath = os.path.join(dirpath, filename)
                    if valid_file(fullpath):
                        symbol_tables.append(read_symboltable(fullpath))

    # Filter None
    symbol_tables = [i for i in symbol_tables if i]

    output("[+] Checking symbol tables for matching symbols")
    for symbol_table in symbol_tables:
        for symbol in symbol_table.get_symbols():
            if symbol.is_imported():
                if symbol.get_name() in IMPORT_SYMBOLS:
                    files_to_check.append(symbol_table._filename)

    if args.list:
        for file_to_check in files_to_check:
            print file_to_check
    else:
        output("[+] Generating man pages")
        for file_to_check in files_to_check:
            manpage = help2man(file_to_check)
            if manpage is not None:
                manname = os.path.basename(file_to_check.replace(".py",
                                                                 ".1{}".format(args.nogz[1])))
                write_manpage(manname, manpage, args.nogz[0])
                output("Wrote manpage for {} to {}".format(file_to_check, manname))
            else:
                output("Cannot create man page for {} - help2man failed!".format(file_to_check))

    return 0


if __name__ == "__main__":
    sys.exit(main())
