#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2019             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# tails. You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

#
# This module is 1.6 only, so not unit-tested
#
from __future__ import print_function
from typing import AnyStr, Tuple, List  # pylint: disable=unused-import

import sys

from hashlib import md5
from Cryptodome.Cipher import AES

# Explicitly check for Python 3 (which is understood by mypy)
if sys.version_info[0] >= 3:
    from pathlib import Path  # pylint: disable=import-error
else:
    from pathlib2 import Path

OBFUSCATE_WORD = "HideAll"
OBFUSCATE_MARK = "CMKE"


# Adapt OpenSSL handling of key and iv
def derive_key_and_iv(password, key_length, iv_length):
    # type: (str, int, int) -> Tuple[str, str]
    d = d_i = ''
    while len(d) < key_length + iv_length:
        md5_block = md5(d_i + password)
        d_i = md5_block.digest()
        d += d_i
    return d[:key_length], d[key_length:key_length + iv_length]


def decrypt_package(encrypted_pkg):
    # type: (AnyStr) -> AnyStr

    key, iv = derive_key_and_iv(OBFUSCATE_WORD, 32, AES.block_size)

    decryption_suite = AES.new(key, AES.MODE_CBC, iv)
    decrypted_pkg = decryption_suite.decrypt(encrypted_pkg)

    return decrypted_pkg


def encrypt_package(pkg):
    # type: (AnyStr) -> AnyStr

    key, iv = derive_key_and_iv(OBFUSCATE_WORD, 32, AES.block_size)

    encryption_suite = AES.new(key, AES.MODE_CBC, iv)
    pad = len(pkg)
    pad = (pad / encryption_suite.block_size + 1) * encryption_suite.block_size
    to_encrypt_pkg = pkg.ljust(pad)
    encrypted_pkg = encryption_suite.encrypt(to_encrypt_pkg)  # type: AnyStr

    # Strip of fill bytes of openssl
    return encrypted_pkg


# used normally only in Windows build chain to patch
def parse_command_line(argv):
    # type: (List[str]) -> Tuple[str, str, str]
    # mode of the
    command = argv[1]

    return command, argv[2], argv[2] if len(argv) <= 3 else argv[3]


def encrypt_file(file_in, file_out):
    # type: (str, str) -> int
    p = Path(file_in)
    if not p.exists():
        return 1

    data = p.read_bytes()  # type: ignore # [attr-defined]
    encrypted_data = encrypt_package(data)  # type: bytes
    if len(encrypted_data) > 0:
        out = Path(file_out)
        with out.open("wb") as f:
            f.write(encrypted_data)

            # marker at the end
            f.write(OBFUSCATE_MARK)
            f.write("{:08d}".format(len(data)))
        return 0

    return 3


def decrypt_file(file_in, file_out):
    # type: (str, str) -> int
    p = Path(file_in)
    if not p.exists():
        return 1

    data_in = p.read_bytes()  # type: ignore # [attr-defined]
    if len(data_in) < 12:
        print("Too short file")
        return 9

    if data_in[-12:-8] != OBFUSCATE_MARK:
        print("No mark")
        return 7

    length = int(data_in[-8:])

    decrypted_data = decrypt_package(data_in[:-12])  # type: bytes
    if len(decrypted_data) > 0:
        out_file = Path(file_out)
        with out_file.open("wb") as f:
            f.write(decrypted_data[:length])
        return 0

    return 3


# MAIN:
if __name__ == '__main__':
    mode, f_name, f_name_out = parse_command_line(sys.argv)

    if mode == "encrypt":
        exit(encrypt_file(f_name, f_name_out))

    if mode == "decrypt":
        exit(decrypt_file(f_name, f_name_out))

    print("Invalid mode '{}'".format(mode))
    exit(1)