#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
import glob
import mock
import os
import unittest
import yaml

from types import SimpleNamespace

from charm import (
    check_for_missing_config_fields,
    create_discourse_pod_config,
    get_pod_spec,
    DiscourseCharm,
)

from ops import testing


def load_configs(directory):
    """Load configs for use by tests.

    Valid and invalid configs are present in the fixtures directory. The files
    contain the juju config, along with the spec that that config should
    produce in the case of valid configs. In the case of invalid configs, they
    contain the juju config and the error that should be triggered by the
    config. These scenarios are tested below. Additional config variations can
    be created by creating an appropriately named config file in the fixtures
    directory. Valid configs should be named: config_valid_###.yaml and invalid
    configs should be named: config_invalid_###.yaml."""
    configs = {}
    for filename in glob.glob(os.path.join(directory, 'config*.yaml')):
        with open(filename) as file:
            name, _ = os.path.splitext(os.path.basename(filename))
            configs[name] = yaml.full_load(file)
    return configs


class TestDiscourseK8sCharmHooksDisabled(unittest.TestCase):
    def setUp(self):
        self.harness = testing.Harness(DiscourseCharm)
        self.harness.disable_hooks()
        self.harness.set_leader(True)
        self.harness.begin()
        self.configs = load_configs(os.path.join(os.path.dirname(__file__), 'fixtures'))

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
        """Test that the entire config process for the charm works."""
        test_config = copy.deepcopy(self.configs['config_valid_complete']['config'])
        test_config['db_user'] = 'discourse_m'
        test_config['db_password'] = 'a_real_password'
        test_config['db_host'] = '10.9.89.237'
        db_event = SimpleNamespace()
        db_event.master = SimpleNamespace()
        db_event.master.user = 'discourse_m'
        db_event.master.password = 'a_real_password'
        db_event.master.host = '10.9.89.237'
        expected_spec = (get_pod_spec(self.harness.charm.framework.model.app.name, test_config), None)
        self.harness.update_config(self.configs['config_valid_complete']['config'])
        self.harness.charm.on_database_relation_joined(db_event)
        self.harness.charm.on_database_changed(db_event)
        configured_spec = self.harness.get_pod_spec()
        self.assertEqual(configured_spec, expected_spec, 'Configured spec does not match expected pod spec.')

    def test_charm_config_process_not_leader(self):
        """Test that the config process on a non-leader does not trigger a pod_spec change."""
        non_leader_harness = testing.Harness(DiscourseCharm)
        non_leader_harness.disable_hooks()
        non_leader_harness.set_leader(False)
        non_leader_harness.begin()

        action_event = mock.Mock()
        non_leader_harness.update_config(self.configs['config_valid_complete']['config'])
        non_leader_harness.charm.configure_pod(action_event)
        result = non_leader_harness.get_pod_spec()
        self.assertEqual(result, None, 'Non-leader does not set pod spec.')

    def test_lost_db_relation(self):
        """Test that losing our DB relation triggers a drop of pod config."""
        self.harness.update_config(self.configs['config_valid_complete']['config'])
        db_event = SimpleNamespace()
        db_event.master = None
        self.harness.charm.on_database_changed(db_event)
        configured_spec = self.harness.get_pod_spec()
        self.assertEqual(configured_spec, None, 'Lost DB relation does not result in empty spec as expected')

    def test_on_database_relation_joined(self):
        """Test joining the DB relation."""
        # First test with a non-leader, confirm the database property isn't set.
        non_leader_harness = testing.Harness(DiscourseCharm)
        non_leader_harness.disable_hooks()
        non_leader_harness.set_leader(False)
        non_leader_harness.begin()

        action_event = mock.Mock()
        action_event.database = None
        non_leader_harness.update_config(self.configs['config_valid_complete']['config'])
        non_leader_harness.charm.on_database_relation_joined(action_event)
        self.assertEqual(action_event.database, None)

        # Now test with a leader, the database property is set.
        self.harness.update_config(self.configs['config_valid_complete']['config'])
        self.harness.charm.on_database_relation_joined(action_event)
        self.assertEqual(action_event.database, "discourse")
