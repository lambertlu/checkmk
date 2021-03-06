#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest  # type: ignore[import]

import cmk.utils.paths
import cmk.utils.version as cmk_version
import cmk.gui.watolib.activate_changes as activate_changes
from cmk.gui.watolib.config_sync import ReplicationPath

import testlib

pytestmark = pytest.mark.usefixtures("load_plugins")


@pytest.fixture(autouse=True)
def restore_orig_replication_paths():
    _orig_paths = activate_changes._replication_paths[:]
    yield
    activate_changes._replication_paths = _orig_paths


def _expected_replication_paths():
    expected = [
        ReplicationPath('dir', 'check_mk', 'etc/check_mk/conf.d/wato/', []),
        ReplicationPath('dir', 'multisite', 'etc/check_mk/multisite.d/wato/', []),
        ReplicationPath('file', 'htpasswd', 'etc/htpasswd', []),
        ReplicationPath('file', 'auth.secret', 'etc/auth.secret', []),
        ReplicationPath('file', 'auth.serials', 'etc/auth.serials', []),
        ReplicationPath('dir', 'usersettings', 'var/check_mk/web', ['*/report-thumbnails']),
        ReplicationPath('dir', 'mkps', 'var/check_mk/packages', []),
        ReplicationPath('dir', 'local', 'local', []),
    ]

    if not cmk_version.is_raw_edition():
        expected += [
            ReplicationPath('dir', 'liveproxyd', 'etc/check_mk/liveproxyd.d/wato/', []),
        ]

    if testlib.is_enterprise_repo():
        expected += [
            ReplicationPath('dir', 'dcd', 'etc/check_mk/dcd.d/wato/', ['distributed.mk']),
            ReplicationPath('dir', 'mknotify', 'etc/check_mk/mknotifyd.d/wato', []),
        ]

    expected += [
        ReplicationPath('dir', 'mkeventd', 'etc/check_mk/mkeventd.d/wato', []),
        ReplicationPath('dir', 'mkeventd_mkp', 'etc/check_mk/mkeventd.d/mkp/rule_packs', []),
        ReplicationPath('file', 'diskspace', 'etc/diskspace.conf', []),
    ]

    if cmk_version.is_managed_edition():
        expected += [
            ReplicationPath(ty='file',
                            ident='customer_check_mk',
                            site_path='etc/check_mk/conf.d/customer.mk',
                            excludes=[]),
            ReplicationPath(ty='file',
                            ident='customer_gui_design',
                            site_path='etc/check_mk/multisite.d/zzz_customer_gui_design.mk',
                            excludes=[]),
            ReplicationPath(ty='file',
                            ident='customer_multisite',
                            site_path='etc/check_mk/multisite.d/customer.mk',
                            excludes=[]),
            ReplicationPath(
                ty='file',
                ident='gui_logo',
                site_path='local/share/check_mk/web/htdocs/themes/classic/images/sidebar_top.png',
                excludes=[]),
            ReplicationPath(
                ty='file',
                ident='gui_logo_dark',
                site_path='local/share/check_mk/web/htdocs/themes/modern-dark/images/mk-logo.png',
                excludes=[]),
            ReplicationPath(
                ty='file',
                ident='gui_logo_facelift',
                site_path='local/share/check_mk/web/htdocs/themes/facelift/images/mk-logo.png',
                excludes=[]),
        ]

    return expected


def test_get_replication_paths_defaults(edition_short, monkeypatch):
    expected = _expected_replication_paths()
    assert sorted(activate_changes.get_replication_paths()) == sorted(expected)


@pytest.mark.parametrize("replicate_ec", [None, True, False])
@pytest.mark.parametrize("replicate_mkps", [None, True, False])
@pytest.mark.parametrize("is_pre_17_remote_site", [True, False])
def test_get_replication_components(edition_short, monkeypatch, replicate_ec, replicate_mkps,
                                    is_pre_17_remote_site):
    partial_site_config = {}
    if replicate_ec is not None:
        partial_site_config["replicate_ec"] = replicate_ec
    if replicate_mkps is not None:
        partial_site_config["replicate_mkps"] = replicate_mkps

    expected = _expected_replication_paths()

    if not replicate_ec:
        expected = [e for e in expected if e.ident not in ["mkeventd", "mkeventd_mkp"]]

    if not replicate_mkps:
        expected = [e for e in expected if e.ident not in ["local", "mkps"]]

    work_dir = cmk.utils.paths.omd_root

    if is_pre_17_remote_site:
        for repl_path in expected:
            if repl_path.ident in {
                    "check_mk", "multisite", "liveproxyd", "mkeventd", "dcd", "mknotify"
            }:
                if "sitespecific.mk" not in repl_path.excludes:
                    repl_path.excludes.append("sitespecific.mk")

        expected += [
            ReplicationPath(
                ty="file",
                ident="sitespecific",
                site_path="site_globals/sitespecific.mk",
                excludes=[],
            ),
        ]

    if not is_pre_17_remote_site:
        expected += [
            ReplicationPath(
                ty='file',
                ident='distributed_wato',
                site_path='etc/check_mk/conf.d/distributed_wato.mk',
                excludes=['.*new*'],
            ),
        ]

    assert sorted(
        activate_changes._get_replication_components(work_dir, partial_site_config,
                                                     is_pre_17_remote_site)) == sorted(expected)


def test_add_replication_paths_pre_17(monkeypatch):
    monkeypatch.setattr(cmk.utils.paths, "omd_root", "/path")
    # dir/file, ident, path, optional list of excludes
    activate_changes.add_replication_paths([
        ("dir", "abc", "/path/to/abc"),
        ("dir", "abc", "/path/to/abc", ["e1", "e2"]),
    ])
    monkeypatch.undo()

    assert activate_changes.get_replication_paths()[-2] == ReplicationPath(
        "dir", "abc", "to/abc", [])
    assert activate_changes.get_replication_paths()[-1] == ReplicationPath(
        "dir", "abc", "to/abc", ["e1", "e2"])


def test_add_replication_paths():
    activate_changes.add_replication_paths([
        ReplicationPath("dir", "abc", "path/to/abc", ["e1", "e2"]),
    ])

    assert activate_changes.get_replication_paths()[-1] == ReplicationPath(
        "dir", "abc", "path/to/abc", ["e1", "e2"])


@pytest.mark.parametrize("expected, site_status", [
    (False, {}),
    (False, {
        "livestatus_version": "1.8.0"
    }),
    (False, {
        "livestatus_version": "1.8.0"
    }),
    (False, {
        "livestatus_version": "1.7.0p2"
    }),
    (False, {
        "livestatus_version": "1.7.0"
    }),
    (False, {
        "livestatus_version": "1.7.0i1"
    }),
    (False, {
        "livestatus_version": "1.7.0-2020.04.20"
    }),
    (True, {
        "livestatus_version": "1.6.0p2"
    }),
    (True, {
        "livestatus_version": "1.5.0p23"
    }),
])
def test_is_pre_17_remote_site(site_status, expected):
    if expected is False:
        pytest.skip("Disabled for the moment")
    assert activate_changes._is_pre_17_remote_site(site_status) == expected
