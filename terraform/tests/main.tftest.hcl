# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic_deploy" {
  variables {
    model_uuid = run.setup_tests.model_uuid
    channel    = "latest/edge"
    # renovate: depName="discourse-k8s"
    revision = 241
  }

  assert {
    condition     = output.app_name == "discourse-k8s"
    error_message = "discourse-k8s app_name did not match expected"
  }
}
