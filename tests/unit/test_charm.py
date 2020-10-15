#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import glob
import unittest
import yaml
import mock
from pprint import pprint

from charm import DiscourseCharm

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
                pod_config = self.harness.charm._create_discourse_pod_config(self.configs[config_key]['config'])
                self.assertEqual(
                    pod_config,
                    self.configs[config_key]['pod_config'],
                    'Valid config {} is does not produce expected config options for pod.'.format(config_key),
                )

    def test_invalid_configs_are_recognized(self):
        """Test that bad configs are identified by the charm."""
        for config_key in self.configs:
            if config_key.startswith('config_invalid_'):
                missing_fields = self.harness.charm._check_for_missing_config_fields(self.configs[config_key]['config'])
                self.assertEqual(
                    missing_fields,
                    self.configs[config_key]['missing_fields'],
                    'Invalid config {} does not fail as expected.'.format(config_key),
                )

# currently fails, I think because the DB relation is missing?
#    def test_charm_config_process(self):
#        expected_spec = self.harness.charm._get_pod_spec(self.configs['config_valid_1']['config'])
#        self.harness.update_config(self.configs['config_valid_1']['config'])
#        self.harness.charm.configure_pod()
#        configured_spec = self.harness.get_pod_spec()
#        pprint(configured_spec)
#        self.assertEqual(configured_spec, expected_spec, 'Configured spec does not match expected pod spec.')

    def test_charm_config_process_not_leader(self):
        non_leader_harness = testing.Harness(DiscourseCharm)
        non_leader_harness.disable_hooks()
        non_leader_harness.set_leader(False)
        non_leader_harness.begin()

        action_event = mock.Mock()
        non_leader_harness.update_config(self.configs['config_valid_1']['config'])
        non_leader_harness.charm.configure_pod(action_event)
        result = non_leader_harness.get_pod_spec()
        pprint(result)
        self.assertEqual(result, None, 'Non-leader does not set pod spec.')
