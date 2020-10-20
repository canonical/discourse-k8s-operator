#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import glob
import unittest
import yaml
import mock
import copy
from types import SimpleNamespace
from pprint import pprint

from charm import DiscourseCharm, create_discourse_pod_config, get_pod_spec, check_for_missing_config_fields

from ops import testing

dirname = os.path.dirname(__file__)


# Valid and Invalid configs are present in the fixtures
# directory. The files contain the juju config, along with
# the spec that that config should produce in the case of
# valid configs. In the case of invalid configs, they contain
# the juju config and the error that should be triggered by
# the config. These scenarios are tested below. Additional
# config variations can be created by creating an appropriately
# named config file in the fixtures directory. Valid configs
# should be named: config_valid_###.yaml and invalid configs
# should be named: config_invalid_###.yaml.
#
# This function loads the configs for use by the tests.
def load_configs(directory):
    configs = {}
    for filename in glob.glob(os.path.join(directory, 'config*.yaml')):
        pprint(filename)
        with open(filename) as file:
            name = os.path.splitext(os.path.basename(filename))
            pprint(name[0])
            configs[name[0]] = yaml.full_load(file)
    return configs


class TestDiscourseK8sCharmHooksDisabled(unittest.TestCase):
    def setUp(self):
        self.harness = testing.Harness(DiscourseCharm)
        self.harness.disable_hooks()
        self.harness.set_leader(True)
        self.harness.begin()
        self.configs = load_configs(os.path.join(dirname, 'fixtures'))

    def test_valid_configs_are_ok(self):
        """Test that a valid config is considered valid."""
        for config_key in self.configs:
            if config_key.startswith('config_valid_'):
                config_valid = self.harness.charm.check_config_is_valid(self.configs[config_key]['config'])
                pod_config = create_discourse_pod_config(self.configs[config_key]['config'])
                self.assertEqual(config_valid, True, 'Valid config is not recognized as valid')
                self.assertEqual(
                    pod_config,
                    self.configs[config_key]['pod_config'],
                    'Valid config {} is does not produce expected config options for pod.'.format(config_key),
                )

    def test_invalid_configs_are_recognized(self):
        """Test that bad configs are identified by the charm."""
        for config_key in self.configs:
            if config_key.startswith('config_invalid_'):
                config_valid = self.harness.charm.check_config_is_valid(self.configs[config_key]['config'])
                missing_fields = check_for_missing_config_fields(self.configs[config_key]['config'])
                self.assertEqual(config_valid, False, 'Invalid config is not recognized as invalid')
                self.assertEqual(
                    missing_fields,
                    self.configs[config_key]['missing_fields'],
                    'Invalid config {} does not fail as expected.'.format(config_key),
                )

    def test_charm_config_process(self):
        test_config = copy.deepcopy(self.configs['config_valid_1']['config'])
        test_config['db_user'] = 'discourse_m'
        test_config['db_password'] = 'a_real_password'
        test_config['db_host'] = '10.9.89.237'
        db_event = SimpleNamespace()
        db_event.master = SimpleNamespace()
        db_event.master.user = 'discourse_m'
        db_event.master.password = 'a_real_password'
        db_event.master.host = '10.9.89.237'
        expected_spec = get_pod_spec(self.harness.charm.framework.model.app.name, test_config)
        self.harness.update_config(self.configs['config_valid_1']['config'])
        self.harness.charm.on_database_relation_joined(db_event)
        self.harness.charm.on_database_changed(db_event)
        configured_spec = self.harness.get_pod_spec()
        self.maxDiff = None
        self.assertEqual(configured_spec[0], expected_spec, 'Configured spec does not match expected pod spec.')

    def test_charm_config_process_not_leader(self):
        non_leader_harness = testing.Harness(DiscourseCharm)
        non_leader_harness.disable_hooks()
        non_leader_harness.set_leader(False)
        non_leader_harness.begin()

        action_event = mock.Mock()
        non_leader_harness.update_config(self.configs['config_valid_1']['config'])
        non_leader_harness.charm.configure_pod(action_event)
        result = non_leader_harness.get_pod_spec()
        self.assertEqual(result, None, 'Non-leader does not set pod spec.')

    def test_lost_db_relation(self):
        self.harness.update_config(self.configs['config_valid_1']['config'])
        db_event = SimpleNamespace()
        db_event.master = None
        self.harness.charm.on_database_changed(db_event)
        configured_spec = self.harness.get_pod_spec()
        self.assertEqual(configured_spec, None, 'Lost DB relation does not result in empty spec as expected')
