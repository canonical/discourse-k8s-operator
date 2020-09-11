#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import os
import glob
import unittest
import yaml
import mock
from pprint import pprint

from charm import (
    DiscourseCharm,
    BlockedStatus
)

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
                self.harness.update_config(self.configs[config_key]['config'])
                valid_config = self.harness.charm.check_config_is_valid(self.configs[config_key]['config'])
                self.assertEqual(valid_config, True, 'Valid config {} is not recognized as valid.'.format(config_key))

    def test_charm_identifies_bad_configs(self):
        """Test that bad configs are identified by the charm."""
        for config_key in self.configs:
            if config_key.startswith('config_invalid_'):
                self.harness.update_config(self.configs[config_key]['config'])
                valid_config = self.harness.charm.check_config_is_valid(self.configs[config_key]['config'])
                self.assertEqual(valid_config, False, 'Bad Config {} is recognized.'.format(config_key))
                self.assertEqual(self.harness.charm.model.unit.status,
                                 BlockedStatus(self.configs[config_key]['expected_error_status']),
                                 'Invalid config {} does not produce correct status'.format(config_key))

    def test_charm_creates_valid_ingress_config(self):
        """Test that a valid config creates a valid ingress spec."""
        for config_key in self.configs:
            if config_key.startswith('config_valid_'):
                self.harness.update_config(self.configs[config_key]['config'])
                spec = self.harness.charm.get_pod_spec(self.configs[config_key]['config'])
                self.assertEqual(spec['kubernetesResources']['ingressResources'],
                                 self.configs[config_key]['spec']['kubernetesResources']['ingressResources'],
                                 'Valid config {} does not produce expected ingress config.'.format(config_key))

    def test_valid_pod_spec(self):
        """A valid config results in a valid pod spec."""
        for config_key in self.configs:
            if config_key.startswith('config_valid_'):
                self.harness.update_config(self.configs[config_key]['config'])
                spec = self.harness.charm.get_pod_spec(self.configs[config_key]['config'])
                self.assertEqual(spec, self.configs[config_key]['spec'],
                                 'Valid config {} does not produce expected pod spec.'.format(config_key))

    def test_charm_config_process(self):
        action_event = mock.Mock()
        self.harness.update_config(self.configs['config_valid_1']['config'])
        self.harness.charm.configure_pod(action_event)
        (configured_spec, k8s_resources) = self.harness.get_pod_spec()
        self.assertEqual(configured_spec, self.configs['config_valid_1']['spec'],
                         'Valid config does not cause charm to set expected pod spec.')

    def test_charm_config_process_invalid_config(self):
        action_event = mock.Mock()
        self.harness.update_config(self.configs['config_invalid_1']['config'])
        self.harness.charm.configure_pod(action_event)
        result = self.harness.get_pod_spec()
        pprint(result)
        self.assertEqual(result, None, 'Invalid config does not get set as pod spec.')

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
