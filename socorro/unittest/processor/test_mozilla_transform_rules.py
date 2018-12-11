# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import copy
import json
import os

from configman.dotdict import DotDict
from mock import call, Mock, patch
import six

from socorro.external.postgresql.connection_context import ConnectionContext
from socorro.lib.datetimeutil import datetime_from_isodate_string
from socorro.lib.revision_data import get_version
from socorro.lib.util import dotdict_to_dict
from socorro.processor.mozilla_transform_rules import (
    AddonsRule,
    BetaVersionRule,
    DatesAndTimesRule,
    ESRVersionRewrite,
    EnvironmentRule,
    ExploitablityRule,
    FlashVersionRule,
    JavaProcessRule,
    MozCrashReasonRule,
    OSPrettyVersionRule,
    OutOfMemoryBinaryRule,
    PluginContentURL,
    PluginRule,
    PluginUserComment,
    ProductRewrite,
    ProductRule,
    SignatureGeneratorRule,
    ThemePrettyNameRule,
    TopMostFilesRule,
    UserDataRule,
    Winsock_LSPRule,
)
from socorro.signature.generator import SignatureGenerator
from socorro.unittest import WHATEVER
from socorro.unittest.processor import get_basic_config, get_basic_processor_meta


canonical_standard_raw_crash = DotDict({
    "uuid": '00000000-0000-0000-0000-000002140504',
    "InstallTime": "1335439892",
    "AdapterVendorID": "0x1002",
    "TotalVirtualMemory": "4294836224",
    "Comments": "why did my browser crash?  #fail",
    "Theme": "classic/1.0",
    "Version": "12.0",
    "Email": "noreply@mozilla.com",
    "Vendor": "Mozilla",
    "EMCheckCompatibility": "true",
    "Throttleable": "1",
    "id": "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}",
    "buildid": "20120420145725",
    "AvailablePageFile": "10641510400",
    "version": "12.0",
    "AdapterDeviceID": "0x7280",
    "ReleaseChannel": "release",
    "submitted_timestamp": "2012-05-08T23:26:33.454482+00:00",
    "URL": "http://www.mozilla.com",
    "timestamp": 1336519593.454627,
    "Notes": "AdapterVendorID: 0x1002, AdapterDeviceID: 0x7280, "
             "AdapterSubsysID: 01821043, "
             "AdapterDriverVersion: 8.593.100.0\nD3D10 Layers? D3D10 "
             "Layers- D3D9 Layers? D3D9 Layers- ",
    "CrashTime": "1336519554",
    "Winsock_LSP": "MSAFD Tcpip [TCP/IPv6] : 2 : 1 :  \n "
                   "MSAFD Tcpip [UDP/IPv6] : 2 : 2 : "
                   "%SystemRoot%\\system32\\mswsock.dll \n "
                   "MSAFD Tcpip [RAW/IPv6] : 2 : 3 :  \n "
                   "MSAFD Tcpip [TCP/IP] : 2 : 1 : "
                   "%SystemRoot%\\system32\\mswsock.dll \n "
                   "MSAFD Tcpip [UDP/IP] : 2 : 2 :  \n "
                   "MSAFD Tcpip [RAW/IP] : 2 : 3 : "
                   "%SystemRoot%\\system32\\mswsock.dll \n "
                   "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
                   "\u0443\u0441\u043b\u0443\u0433 RSVP TCPv6 : 2 : 1 :  \n "
                   "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
                   "\u0443\u0441\u043b\u0443\u0433 RSVP TCP : 2 : 1 : "
                   "%SystemRoot%\\system32\\mswsock.dll \n "
                   "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
                   "\u0443\u0441\u043b\u0443\u0433 RSVP UDPv6 : 2 : 2 :  \n "
                   "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
                   "\u0443\u0441\u043b\u0443\u0433 RSVP UDP : 2 : 2 : "
                   "%SystemRoot%\\system32\\mswsock.dll",
    "FramePoisonBase": "00000000f0de0000",
    "AvailablePhysicalMemory": "2227773440",
    "FramePoisonSize": "65536",
    "StartupTime": "1336499438",
    "Add-ons": "adblockpopups@jessehakanen.net:0.3,"
               "dmpluginff%40westbyte.com:1%2C4.8,"
               "firebug@software.joehewitt.com:1.9.1,"
               "killjasmin@pierros14.com:2.4,"
               "support@surfanonymous-free.com:1.0,"
               "uploader@adblockfilters.mozdev.org:2.1,"
               "{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107,"
               "{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3,"
               "anttoolbar@ant.com:2.4.6.4,"
               "{972ce4c6-7e08-4474-a285-3208198ce6fd}:12.0,"
               "elemhidehelper@adblockplus.org:1.2.1",
    "BuildID": "20120420145725",
    "SecondsSinceLastCrash": "86985",
    "ProductName": "Firefox",
    "legacy_processing": 0,
    "AvailableVirtualMemory": "3812708352",
    "SystemMemoryUsePercentage": "48",
    "ProductID": "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}",
    "Distributor": "Mozilla",
    "Distributor_version": "12.0",
})

canonical_processed_crash = DotDict({
    'json_dump': {
        'sensitive': {
            'exploitability': 'high'
        },
        'modules': [
            {
                "end_addr": "0x12e6000",
                "filename": "plugin-container.exe",
                "version": "26.0.0.5084",
                "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                "debug_file": "plugin-container.pdb",
                "base_addr": "0x12e0000"
            },
            {
                "end_addr": "0x12e6000",
                "filename": "plugin-container.exe",
                "version": "26.0.0.5084",
                "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                "debug_file": "plugin-container.pdb",
                "base_addr": "0x12e0000"
            },
            {
                "end_addr": "0x12e6000",
                "filename": "FlashPlayerPlugin9_1_3_08.exe",
                "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                "debug_file": "plugin-container.pdb",
                "base_addr": "0x12e0000"
            },
            {
                "end_addr": "0x12e6000",
                "filename": "plugin-container.exe",
                "version": "26.0.0.5084",
                "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                "debug_file": "plugin-container.pdb",
                "base_addr": "0x12e0000"
            },
        ]
    }
})


class TestProductRule(object):
    def test_everything_we_hoped_for(self):
        # does it even instantiate?
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ProductRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.product == "Firefox"
        assert processed_crash.version == "12.0"
        assert processed_crash.productid == "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}"
        assert processed_crash.distributor == "Mozilla"
        assert processed_crash.distributor_version == "12.0"
        assert processed_crash.release_channel == "release"
        assert processed_crash.build == "20120420145725"

    def test_stuff_missing(self):
        # does it even instantiate?
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.Version
        del raw_crash.Distributor
        del raw_crash.Distributor_version
        del raw_crash.ReleaseChannel

        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ProductRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.product == "Firefox"
        assert processed_crash.version == ""
        assert processed_crash.productid == "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}"
        assert processed_crash.distributor is None
        assert processed_crash.distributor_version is None
        assert processed_crash.release_channel == ""
        assert processed_crash.build == "20120420145725"


class TestUserDataRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = UserDataRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.url == "http://www.mozilla.com"
        assert processed_crash.user_comments == "why did my browser crash?  #fail"
        assert processed_crash.email == "noreply@mozilla.com"
        assert processed_crash.user_id == ""

    def test_stuff_missing(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.URL
        del raw_crash.Comments
        del raw_crash.Email

        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = UserDataRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.url is None
        assert processed_crash.user_comments is None
        assert processed_crash.email is None


class TestEnvironmentRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = EnvironmentRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.app_notes == raw_crash.Notes

    def test_stuff_missing(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.Notes

        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = EnvironmentRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.app_notes == ""


class TestPluginRule(object):
    def test_plugin_hang(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.PluginHang = 1
        raw_crash.Hang = 0
        raw_crash.ProcessType = 'plugin'
        raw_crash.PluginFilename = 'x.exe'
        raw_crash.PluginName = 'X'
        raw_crash.PluginVersion = '0.0'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.hangid == 'fake-00000000-0000-0000-0000-000002140504'
        assert processed_crash.hang_type == -1
        assert processed_crash.process_type == 'plugin'
        assert processed_crash.PluginFilename == 'x.exe'
        assert processed_crash.PluginName == 'X'
        assert processed_crash.PluginVersion == '0.0'

    def test_browser_hang(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.Hang = 1
        raw_crash.ProcessType = 'browser'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.hangid is None
        assert processed_crash.hang_type == 1
        assert processed_crash.process_type == 'browser'
        assert 'PluginFilename' not in processed_crash
        assert 'PluginName' not in processed_crash
        assert 'PluginVersion' not in processed_crash


class TestAddonsRule(object):
    def test_action_nothing_unexpected(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        addons_rule = AddonsRule(config)
        addons_rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # the raw crash & raw_dumps should not have changed
        assert raw_crash == canonical_standard_raw_crash
        assert raw_dumps == {}

        expected_addon_list = [
            'adblockpopups@jessehakanen.net:0.3',
            'dmpluginff@westbyte.com:1,4.8',
            'firebug@software.joehewitt.com:1.9.1',
            'killjasmin@pierros14.com:2.4',
            'support@surfanonymous-free.com:1.0',
            'uploader@adblockfilters.mozdev.org:2.1',
            '{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107',
            '{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3',
            'anttoolbar@ant.com:2.4.6.4',
            '{972ce4c6-7e08-4474-a285-3208198ce6fd}:12.0',
            'elemhidehelper@adblockplus.org:1.2.1',
        ]
        assert processed_crash.addons == expected_addon_list
        assert processed_crash.addons_checked

    def test_action_colon_in_addon_version(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash['Add-ons'] = 'adblockpopups@jessehakanen.net:0:3:1'
        raw_crash['EMCheckCompatibility'] = 'Nope'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        addons_rule = AddonsRule(config)
        addons_rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected_addon_list = [
            'adblockpopups@jessehakanen.net:0:3:1',
        ]
        assert processed_crash.addons == expected_addon_list
        assert not processed_crash.addons_checked

    def test_action_addon_is_nonsense(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash['Add-ons'] = 'naoenut813teq;mz;<[`19ntaotannn8999anxse `'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        addons_rule = AddonsRule(config)
        addons_rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected_addon_list = [
            'naoenut813teq;mz;<[`19ntaotannn8999anxse `:NO_VERSION',
        ]
        assert processed_crash.addons == expected_addon_list
        assert processed_crash.addons_checked


class TestDatesAndTimesRule(object):
    def test_get_truncate_or_warn(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        processor_notes = []
        ret = DatesAndTimesRule._get_truncate_or_warn(
            raw_crash,
            'submitted_timestamp',
            processor_notes,
            '',
            50
        )
        assert ret == "2012-05-08T23:26:33.454482+00:00"
        assert processor_notes == []

        processor_notes = []
        ret = DatesAndTimesRule._get_truncate_or_warn(
            raw_crash,
            'terrible_timestamp',
            processor_notes,
            "2012-05-08T23:26:33.454482+00:00",
            '50'
        )
        assert ret == "2012-05-08T23:26:33.454482+00:00"
        assert processor_notes == ['WARNING: raw_crash missing terrible_timestamp']

        raw_crash.submitted_timestamp = 17
        processor_notes = []
        ret = DatesAndTimesRule._get_truncate_or_warn(
            raw_crash,
            'submitted_timestamp',
            processor_notes,
            "2012-05-08T23:26:33.454482+00:00",
            '50'
        )
        assert ret == "2012-05-08T23:26:33.454482+00:00"
        # The warning message you get comes from a ValueError
        # which is phrased differently in python 2.6 compared to 2.7.
        # So we need to expect different things depend on python version.
        try:
            42[:1]
        except TypeError as err:
            type_error_value = str(err)
        expected = [
            "WARNING: raw_crash[submitted_timestamp] contains unexpected "
            "value: 17; %s" % type_error_value
        ]
        assert processor_notes == expected

    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash == 86985

    def test_bad_timestamp(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.timestamp = 'hi there'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == ['non-integer value of "timestamp"']

    def test_bad_timestamp_and_no_crash_time(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.timestamp = 'hi there'
        del raw_crash.CrashTime
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 0
        expected = datetime_from_isodate_string('1970-01-01 00:00:00+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == -1335439892
        assert processed_crash.uptime == 0
        assert processed_crash.last_crash == 86985

        expected = [
            'non-integer value of "timestamp"',
            'WARNING: raw_crash missing CrashTime'
        ]
        assert processor_meta.processor_notes == expected

    def test_no_startup_time_bad_timestamp(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.timestamp = 'hi there'
        del raw_crash.StartupTime
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 0
        assert processed_crash.last_crash == 86985

        expected = [
            'non-integer value of "timestamp"',
        ]
        assert processor_meta.processor_notes == expected

    def test_no_startup_time(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.StartupTime
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 0
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == []

    def test_bad_startup_time(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.StartupTime = 'feed the goats'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 1336519554
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == ['non-integer value of "StartupTime"']

    def test_bad_install_time(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.InstallTime = 'feed the goats'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1336519554
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == ['non-integer value of "InstallTime"']

    def test_bad_seconds_since_last_crash(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.SecondsSinceLastCrash = 'feed the goats'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string('2012-05-08 23:25:54+00:00')
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash is None
        assert processor_meta.processor_notes == ['non-integer value of "SecondsSinceLastCrash"']


class TestJavaProcessRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = {
            'JavaStackTrace': (
                'Exception: some messge\n'
                '\tat org.File.function(File.java:100)\n'
                '\tCaused by: Exception: some other message\n'
                '\t\tat org.File.function(File.java:100)'
            )
        }
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = JavaProcessRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # The entire JavaStackTrace blob
        assert processed_crash['java_stack_trace_full'] == raw_crash['JavaStackTrace']

        # Everything except the exception message and "Caused by" section
        # which can contain PII
        assert (
            processed_crash['java_stack_trace'] ==
            'Exception\n\tat org.File.function(File.java:100)'
        )

    def test_malformed(self):
        config = get_basic_config()

        raw_crash = {
            'JavaStackTrace': 'junk\n\tat org.File.function\njunk'
        }

        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = JavaProcessRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # The entire JavaStackTrace blob
        assert processed_crash['java_stack_trace_full'] == raw_crash['JavaStackTrace']

        # The data is malformed, so this should just show "malformed"
        assert processed_crash['java_stack_trace'] == 'malformed'

        # Make sure there's a note in the notes about it
        assert 'malformed java stack trace' in processor_meta.processor_notes[0]


class TestMozCrashReasonRule(object):
    def test_no_mozcrashreason(self):
        config = get_basic_config()

        raw_crash = {}
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = MozCrashReasonRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash == {}

    def test_good_mozcrashreason(self):
        config = get_basic_config()

        raw_crash = {
            'MozCrashReason': 'MOZ_CRASH(OOM)'
        }
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = MozCrashReasonRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash == {
            'moz_crash_reason_raw': 'MOZ_CRASH(OOM)',
            'moz_crash_reason': 'MOZ_CRASH(OOM)'
        }

    def test_bad_mozcrashreason(self):
        config = get_basic_config()
        rule = MozCrashReasonRule(config)

        bad_reasons = [
            'byte index 21548 is not a char boundary',
            'Failed to load module "jar:file..."'
        ]
        for reason in bad_reasons:
            raw_crash = {
                'MozCrashReason': reason
            }
            raw_dumps = {}
            processed_crash = {}
            processor_meta = get_basic_processor_meta()

            rule.action(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert processed_crash == {
                'moz_crash_reason_raw': reason,
                'moz_crash_reason': 'sanitized--see moz_crash_reason_raw'
            }


class TestOutOfMemoryBinaryRule(object):
    def test_extract_memory_info(self):
        config = DotDict()
        config.logger = Mock()

        processor_meta = get_basic_processor_meta()

        with patch('socorro.processor.mozilla_transform_rules.gzip.open') as mocked_gzip_open:
            ret = json.dumps({'mysterious': ['awesome', 'memory']})
            mocked_gzip_open.return_value = six.BytesIO(ret.encode('utf-8'))
            rule = OutOfMemoryBinaryRule(config)
            # Stomp on the value to make it easier to test with
            rule.MAX_SIZE_UNCOMPRESSED = 1024
            memory = rule._extract_memory_info('a_pathname', processor_meta.processor_notes)
            mocked_gzip_open.assert_called_with('a_pathname', 'rb')
            assert memory == {'mysterious': ['awesome', 'memory']}

    def test_extract_memory_info_too_big(self):
        config = DotDict()
        config.logger = Mock()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {'memory_report': 'a_pathname'}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        with patch('socorro.processor.mozilla_transform_rules.gzip.open') as mocked_gzip_open:
            opened = Mock()
            opened.read.return_value = json.dumps({
                'some': 'notveryshortpieceofjson'
            })

            def gzip_open(filename, mode):
                assert mode == 'rb'
                return opened

            mocked_gzip_open.side_effect = gzip_open
            rule = OutOfMemoryBinaryRule(config)

            # Stomp on the value to make it easier to test with
            rule.MAX_SIZE_UNCOMPRESSED = 5

            memory = rule._extract_memory_info('a_pathname', processor_meta.processor_notes)
            expected_error_message = (
                "Uncompressed memory info too large %d (max: %s)" % (
                    35, rule.MAX_SIZE_UNCOMPRESSED
                )
            )
            assert memory == {"ERROR": expected_error_message}
            assert processor_meta.processor_notes == [expected_error_message]
            opened.close.assert_called_with()

            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert 'memory_report' not in processed_crash
            assert processed_crash.memory_report_error == expected_error_message

    def test_extract_memory_info_with_trouble(self):
        config = DotDict()
        config.max_size_uncompressed = 1024
        config.logger = Mock()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {'memory_report': 'a_pathname'}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        with patch('socorro.processor.mozilla_transform_rules.gzip.open') as mocked_gzip_open:
            mocked_gzip_open.side_effect = IOError
            rule = OutOfMemoryBinaryRule(config)

            memory = rule._extract_memory_info('a_pathname', processor_meta.processor_notes)
            assert memory['ERROR'] == 'error in gzip for a_pathname: OSError()'
            assert processor_meta.processor_notes == ['error in gzip for a_pathname: OSError()']

            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert 'memory_report' not in processed_crash
            assert processed_crash.memory_report_error == 'error in gzip for a_pathname: OSError()'

    def test_extract_memory_info_with_json_trouble(self):
        config = DotDict()
        config.max_size_uncompressed = 1024
        config.logger = Mock()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {'memory_report': 'a_pathname'}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        with patch('socorro.processor.mozilla_transform_rules.gzip.open') as mocked_gzip_open:
            with patch(
                'socorro.processor.mozilla_transform_rules.json.loads'
            ) as mocked_json_loads:
                mocked_json_loads.side_effect = ValueError

                rule = OutOfMemoryBinaryRule(config)
                memory = rule._extract_memory_info('a_pathname', processor_meta.processor_notes)
                mocked_gzip_open.assert_called_with('a_pathname', 'rb')
                assert memory == {"ERROR": "error in json for a_pathname: ValueError()"}
                expected = ["error in json for a_pathname: ValueError()"]
                assert processor_meta.processor_notes == expected
                mocked_gzip_open.return_value.close.assert_called_with()

                rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
                assert 'memory_report' not in processed_crash
                expected = 'error in json for a_pathname: ValueError()'
                assert processed_crash.memory_report_error == expected

    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {'memory_report': 'a_pathname'}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        class MyOutOfMemoryBinaryRule(OutOfMemoryBinaryRule):
            @staticmethod
            def _extract_memory_info(dump_pathname, processor_notes):
                assert dump_pathname == raw_dumps['memory_report']
                assert processor_notes == []
                return 'mysterious-awesome-memory'

        with patch('socorro.processor.mozilla_transform_rules.temp_file_context'):
            rule = MyOutOfMemoryBinaryRule(config)
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert processed_crash.memory_report == 'mysterious-awesome-memory'

    def test_this_is_not_the_crash_you_are_looking_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = OutOfMemoryBinaryRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert 'memory_report' not in processed_crash


class TestProductRewriteRule(object):
    def test_product_map_rewrite(self):
        config = get_basic_config()
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash['ProductName'] = 'Fennec'
        raw_crash['ProductID'] = '{aa3c5121-dab2-40e2-81ca-7ea25febc110}'
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ProductRewrite(config)
        rule.act(raw_crash, {}, processed_crash, processor_meta)

        assert raw_crash.ProductName == 'FennecAndroid'
        assert raw_crash.OriginalProductName == 'Fennec'

        # processed_crash should be unchanged
        assert processed_crash == DotDict()
        assert processor_meta.processor_notes == [
            "Rewriting ProductName from 'Fennec' to 'FennecAndroid'"
        ]


class TestESRVersionRewrite(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.ReleaseChannel = 'esr'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ESRVersionRewrite(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Version == "12.0esr"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_not_the_crash_you_are_looking_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.ReleaseChannel = 'not_esr'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ESRVersionRewrite(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Version == "12.0"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_really_broken(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.ReleaseChannel = 'esr'
        del raw_crash.Version
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ESRVersionRewrite(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert "Version" not in raw_crash
        assert processor_meta.processor_notes == ['"Version" missing from esr release raw_crash']

        # processed_crash should be unchanged
        assert processed_crash == DotDict()


class TestPluginContentURL(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.PluginContentURL = 'http://mozilla.com'
        raw_crash.URL = 'http://google.com'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginContentURL(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.URL == "http://mozilla.com"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_not_the_crash_you_are_looking_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.URL = 'http://google.com'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginContentURL(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.URL == "http://google.com"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()


class TestPluginUserComment(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.PluginUserComment = 'I hate it when this happens'
        raw_crash.Comments = 'I wrote something here, too'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginUserComment(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Comments == 'I hate it when this happens'

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_not_the_crash_you_are_looking_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.Comments = 'I wrote something here'
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginUserComment(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Comments == 'I wrote something here'

        # processed_crash should be unchanged
        assert processed_crash == DotDict()


class TestExploitablityRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = copy.deepcopy(canonical_processed_crash)
        processor_meta = get_basic_processor_meta()

        rule = ExploitablityRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.exploitability == 'high'

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash

    def test_this_is_not_the_crash_you_are_looking_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ExploitablityRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.exploitability == 'unknown'

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash


class TestFlashVersionRule(object):
    def test_get_flash_version(self):
        config = get_basic_config()

        rule = FlashVersionRule(config)

        assert rule._get_flash_version(filename='NPSWF32_1_2_3.dll', version='1.2.3') == '1.2.3'
        assert rule._get_flash_version(filename='NPSWF32_1_2_3.dll') == '1.2.3'

        data = rule._get_flash_version(filename='FlashPlayerPlugin_2_3_4.exe', version='2.3.4')
        assert data == '2.3.4'
        assert rule._get_flash_version(filename='FlashPlayerPlugin_2_3_4.exe') == '2.3.4'

        data = rule._get_flash_version(filename='libflashplayer3.4.5.so', version='3.4.5')
        assert data == '3.4.5'
        assert rule._get_flash_version(filename='libflashplayer3.4.5.so') == '3.4.5'

        assert rule._get_flash_version(filename='Flash Player-', version='4.5.6') == '4.5.6'
        assert rule._get_flash_version(filename='Flash Player-.4.5.6') == '.4.5.6'

        ret = rule._get_flash_version(
            filename='Flash Player-',
            version='.4.5.6',
            debug_id='83CF4DC03621B778E931FC713889E8F10'
        )
        assert ret == '.4.5.6'
        ret = rule._get_flash_version(
            filename='Flash Player-.4.5.6',
            debug_id='83CF4DC03621B778E931FC713889E8F10'
        )
        assert ret == '.4.5.6'
        ret = rule._get_flash_version(
            filename='Flash Player-',
            debug_id='83CF4DC03621B778E931FC713889E8F10'
        )
        assert ret == '9.0.16.0'

    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = copy.deepcopy(canonical_processed_crash)
        processor_meta = get_basic_processor_meta()

        rule = FlashVersionRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.flash_version == '9.1.3.08'

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash


class TestWinsock_LSPRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.Winsock_LSP = 'really long string'
        expected_raw_crash = copy.deepcopy(raw_crash)
        raw_dumps = {}
        processed_crash = copy.deepcopy(canonical_processed_crash)
        processor_meta = get_basic_processor_meta()

        rule = Winsock_LSPRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.Winsock_LSP == 'really long string'

        # raw_crash should be unchanged
        assert raw_crash == expected_raw_crash

    def test_missing_key(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.Winsock_LSP
        expected_raw_crash = copy.deepcopy(raw_crash)
        raw_dumps = {}
        processed_crash = copy.deepcopy(canonical_processed_crash)
        processor_meta = get_basic_processor_meta()

        rule = Winsock_LSPRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.Winsock_LSP is None

        # raw_crash should be unchanged
        assert raw_crash == expected_raw_crash


class TestTopMostFilesRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processed_crash.json_dump = {
            'crash_info': {
                'crashing_thread': 0
            },
            'crashing_thread': {
                'frames': [
                    {
                        'source': 'not-the-right-file.dll'
                    },
                    {
                        'file': 'not-the-right-file.cpp'
                    },
                ]
            },
            'threads': [
                {
                    'frames': [
                        {
                            'source': 'dwight.dll'
                        },
                        {
                            'file': 'wilma.cpp'
                        },
                    ]
                },
            ]
        }

        processor_meta = get_basic_processor_meta()

        rule = TopMostFilesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.topmost_filenames == 'wilma.cpp'

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash

    def test_missing_key(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        expected_raw_crash = copy.deepcopy(raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = TopMostFilesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.topmost_filenames is None

        # raw_crash should be unchanged
        assert raw_crash == expected_raw_crash

    def test_missing_key_2(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processed_crash.json_dump = {
            'crashing_thread': {
                'frames': [
                    {
                        'filename': 'dwight.dll'
                    },
                    {
                        'filename': 'wilma.cpp'
                    }
                ]
            }
        }

        processor_meta = get_basic_processor_meta()

        rule = TopMostFilesRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.topmost_filenames is None

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash


class TestBetaVersionRule(object):
    def get_config(self):
        config = get_basic_config()
        config.database_port = os.environ['database_port']
        config.database_hostname = os.environ['database_hostname']
        config.database_name = os.environ['database_name']
        config.database_username = os.environ['database_username']
        config.database_password = os.environ['database_password']
        config.database_class = ConnectionContext
        return config

    def insert_product_version(self, conn, product, channel, build_id, version_string):
        cursor = conn.cursor()
        sql = """
        INSERT INTO crashstats_productversion
            (product_name, release_channel, major_version, release_version,
            version_string, build_id, archive_url)
        VALUES
            (%(product_name)s, %(release_channel)s, %(major_version)s, %(release_version)s,
            %(version_string)s, %(build_id)s, %(archive_url)s)
        """
        params = {
            'product_name': product,
            'release_channel': channel,
            'build_id': build_id,
            'major_version': int(version_string.split('.')[0]),
            'release_version': version_string.split('.')[0],
            'version_string': version_string,
            'archive_url': 'test',
        }
        cursor.execute(sql, params)
        conn.commit()

    def test_beta_channel_known_version(self, db_conn):
        # Beta channel with known version gets converted correctly
        config = self.get_config()

        self.insert_product_version(
            conn=db_conn,
            product='Firefox',
            channel='beta',
            build_id='20001001101010',
            version_string='3.0b1'
        )

        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            'product': 'Firefox',
            'release_channel': 'beta',
            'version': '3.0',
            'build': '20001001101010',
        }
        processor_meta = get_basic_processor_meta()

        rule = BetaVersionRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash['version'] == '3.0b1'
        assert processor_meta.processor_notes == []

    def test_release_channel(self):
        """Release channel doesn't trigger rule"""
        config = self.get_config()
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            'product': 'Firefox',
            'version': '2.0',
            'release_channel': 'release',
            'build': '20000801101010',
        }
        processor_meta = get_basic_processor_meta()

        rule = BetaVersionRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash['version'] == '2.0'
        assert len(processor_meta.processor_notes) == 0

    def test_nightly_channel(self):
        """Nightly channel doesn't trigger rule"""
        config = self.get_config()
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            'product': 'Firefox',
            'version': '5.0a1',
            'release_channel': 'nightly',
            'build': '20000105101010',
        }
        processor_meta = get_basic_processor_meta()

        rule = BetaVersionRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash['version'] == '5.0a1'
        assert processor_meta.processor_notes == []

    def test_bad_buildid(self):
        """Invalid buildids don't cause errors"""
        config = self.get_config()
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            'product': 'Firefox',
            'release_channel': 'beta',
            'version': '5.0',
            'build': '2",381,,"',
        }
        processor_meta = get_basic_processor_meta()

        rule = BetaVersionRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash['version'] == '5.0b0'
        assert processor_meta.processor_notes == [
            'release channel is beta but no version data was found - '
            'added "b0" suffix to version number'
        ]

    def test_beta_channel_unknown_version(self):
        """Beta crash that Buildhub doesn't know about gets b0"""
        config = self.get_config()
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            'product': 'Firefox',
            'version': '3.0.1',
            'release_channel': 'beta',
            'build': '220000101101011',
        }
        processor_meta = get_basic_processor_meta()

        rule = BetaVersionRule(config)
        rule.action(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash['version'] == '3.0.1b0'
        assert processor_meta.processor_notes == [
            'release channel is beta but no version data was found - '
            'added "b0" suffix to version number'
        ]

    def test_aurora_channel(self, db_conn):
        """Test aurora channel lookup"""
        self.insert_product_version(
            conn=db_conn,
            product='Firefox',
            channel='aurora',
            build_id='20001001101010',
            version_string='3.0b1'
        )

        config = self.get_config()
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            'product': 'Firefox',
            'version': '3.0',
            'release_channel': 'aurora',
            'build': '20001001101010',
        }
        processor_meta = get_basic_processor_meta()

        rule = BetaVersionRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash['version'] == '3.0b1'
        assert processor_meta.processor_notes == []


class TestOsPrettyName(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}

        processor_meta = get_basic_processor_meta()

        rule = OSPrettyVersionRule(config)

        # A known Windows version.
        processed_crash = DotDict()
        processed_crash.os_name = 'Windows NT'
        processed_crash.os_version = '10.0.11.7600'

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'Windows 10'

        # An unknown Windows version.
        processed_crash = DotDict()
        processed_crash.os_name = 'Windows NT'
        processed_crash.os_version = '15.2'

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'Windows Unknown'

        # A valid version of Mac OS X.
        processed_crash = DotDict()
        processed_crash.os_name = 'Mac OS X'
        processed_crash.os_version = '10.18.324'

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'OS X 10.18'

        # An invalid version of Mac OS X.
        processed_crash = DotDict()
        processed_crash.os_name = 'Mac OS X'
        processed_crash.os_version = '12.1'

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'OS X Unknown'

        # Any version of Linux.
        processed_crash = DotDict()
        processed_crash.os_name = 'Linux'
        processed_crash.os_version = '0.0.12.13'

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'Linux'

        # Now try some bogus processed_crashes.
        processed_crash = DotDict()
        processed_crash.os_name = 'Lunix'
        processed_crash.os_version = None

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'Lunix'

        processed_crash = DotDict()
        processed_crash.os_name = None
        processed_crash.os_version = None

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] is None

        processed_crash = DotDict()

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] is None

        processed_crash = DotDict()
        processed_crash.os_name = 'Windows NT'
        processed_crash.os_version = 'NaN'

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert 'os_pretty_version' in processed_crash
        assert processed_crash['os_pretty_version'] == 'Windows NT'


class TestThemePrettyNameRule(object):
    def test_everything_we_hoped_for(self):
        config = get_basic_config()

        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()
        processed_crash.addons = [
            'adblockpopups@jessehakanen.net:0.3',
            'dmpluginff@westbyte.com:1,4.8',
            'firebug@software.joehewitt.com:1.9.1',
            'killjasmin@pierros14.com:2.4',
            'support@surfanonymous-free.com:1.0',
            'uploader@adblockfilters.mozdev.org:2.1',
            '{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107',
            '{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3',
            'anttoolbar@ant.com:2.4.6.4',
            '{972ce4c6-7e08-4474-a285-3208198ce6fd}:12.0',
            'elemhidehelper@adblockplus.org:1.2.1',
        ]

        rule = ThemePrettyNameRule(config)
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # the raw crash & raw_dumps should not have changed
        assert dotdict_to_dict(raw_crash) == dotdict_to_dict(canonical_standard_raw_crash)
        assert raw_dumps == {}

        expected_addon_list = [
            'adblockpopups@jessehakanen.net:0.3',
            'dmpluginff@westbyte.com:1,4.8',
            'firebug@software.joehewitt.com:1.9.1',
            'killjasmin@pierros14.com:2.4',
            'support@surfanonymous-free.com:1.0',
            'uploader@adblockfilters.mozdev.org:2.1',
            '{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107',
            '{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3',
            'anttoolbar@ant.com:2.4.6.4',
            '{972ce4c6-7e08-4474-a285-3208198ce6fd} (default theme):12.0',
            'elemhidehelper@adblockplus.org:1.2.1',
        ]
        assert processed_crash.addons == expected_addon_list

    def test_missing_key(self):
        config = get_basic_config()

        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ThemePrettyNameRule(config)

        # Test with missing key.
        res = rule.predicate({}, {}, processed_crash, processor_meta)
        assert res is False

        # Test with empty list.
        processed_crash.addons = []
        res = rule.predicate({}, {}, processed_crash, processor_meta)
        assert res is False

        # Test with key missing from list.
        processed_crash.addons = [
            'adblockpopups@jessehakanen.net:0.3',
            'dmpluginff@westbyte.com:1,4.8',
        ]
        res = rule.predicate({}, {}, processed_crash, processor_meta)
        assert res is False

    def test_with_malformed_addons_field(self):
        config = get_basic_config()
        rule = ThemePrettyNameRule(config)

        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        processed_crash.addons = [
            'addon_with_no_version',
            '{972ce4c6-7e08-4474-a285-3208198ce6fd}',
            'elemhidehelper@adblockplus.org:1.2.1',
        ]
        rule.act({}, {}, processed_crash, processor_meta)

        expected_addon_list = [
            'addon_with_no_version',
            '{972ce4c6-7e08-4474-a285-3208198ce6fd} (default theme)',
            'elemhidehelper@adblockplus.org:1.2.1',
        ]
        assert processed_crash.addons == expected_addon_list


class TestSignatureGeneratorRule:
    def test_signature(self):
        rule = SignatureGeneratorRule(get_basic_config())
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        processed_crash = DotDict({
            'json_dump': {
                'crash_info': {
                    'crashing_thread': 0
                },
                'crashing_thread': 0,
                'threads': [
                    {
                        'frames': [
                            {
                                'frame': 0,
                                'function': 'Alpha<Bravo<Charlie>, Delta>::Echo<Foxtrot>',
                                'file': 'foo.cpp',
                            },
                            {
                                'frame': 1,
                                'function': 'std::something::something',
                                'file': 'foo.rs',
                            },
                        ]
                    },
                ]
            }
        })
        processor_meta = get_basic_processor_meta()

        rule.action(raw_crash, {}, processed_crash, processor_meta)

        assert processed_crash['signature'] == 'Alpha<T>::Echo<T>'
        assert processed_crash['proto_signature'] == 'Alpha<T>::Echo<T> | std::something::something'
        assert processor_meta['processor_notes'] == []

    def test_empty_raw_and_processed_crashes(self):
        rule = SignatureGeneratorRule(get_basic_config())
        raw_crash = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule.action(raw_crash, {}, processed_crash, processor_meta)

        # NOTE(willkg): This is what the current pipeline yields. If any of
        # those parts change, this might change, too. The point of this test is
        # that we can pass in empty dicts and the SignatureGeneratorRule and
        # the generation rules in the default pipeline don't fall over.
        assert processed_crash['signature'] == 'EMPTY: no crashing thread identified'
        assert 'proto_signature' not in processed_crash
        assert processor_meta['processor_notes'] == [
            'CSignatureTool: No signature could be created because we do not know '
            'which thread crashed'
        ]

    @patch('socorro.lib.raven_client.raven')
    def test_rule_fail_and_capture_error(self, mock_raven):
        exc_value = Exception('Cough')

        class BadRule(object):
            def predicate(self, raw_crash, processed_crash):
                raise exc_value

        version = get_version()
        sentry_dsn = 'https://username:password@sentry.example.com/'

        config = get_basic_config()
        config.sentry = DotDict()
        config.sentry.dsn = sentry_dsn
        rule = SignatureGeneratorRule(config)

        # Override the regular SigntureGenerator with one with a BadRule
        # in the pipeline
        rule.generator = SignatureGenerator(
            pipeline=[BadRule()],
            error_handler=rule._error_handler
        )

        raw_crash = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule.action(raw_crash, {}, processed_crash, processor_meta)

        # NOTE(willkg): The signature is an empty string because there are no
        # working rules that add anything to it.
        assert processed_crash['signature'] == ''
        assert 'proto_signature' not in processed_crash
        assert processor_meta['processor_notes'] == [
            'Rule BadRule failed: Cough'
        ]

        # Make sure the client was instantiated with the sentry_dsn
        mock_raven.Client.assert_called_once_with(dsn=sentry_dsn, release=version)

        # Make sure captureExeption was called with the right args.
        assert (
            mock_raven.Client().captureException.call_args_list == [
                call((Exception, exc_value, WHATEVER))
            ]
        )
