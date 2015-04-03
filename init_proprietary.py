#!/usr/bin/python-init

import argparse

"""
A script to remove all proprietary files and directories from a directory.
Used to push a clean repository to github and to build packages without
init proprietary code.
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="The directory to clean")
