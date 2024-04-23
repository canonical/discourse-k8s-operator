# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface for interactions with discourse."""
import logging
import tempfile
import typing

import yaml
from ops.pebble import ExecError, ExecProcess

CONTAINER_APP_USERNAME = "_daemon_"
DISCOURSE_PATH = "/srv/discourse/app"

logger = logging.getLogger(__name__)


def update_site_settings(
    container, environment: typing.Dict[str, str], settings: typing.Dict[str, str]
) -> None:
    """Update discourse site_settings."""
    try:
        # create a tempfile to store the yaml site_settings
        with tempfile.NamedTemporaryFile() as fp:
            yaml.dump(settings, fp, allow_unicode=True)
            process: ExecProcess = container.exec(
                [
                    f"{DISCOURSE_PATH}/bin/bundle",
                    "exec",
                    "rake",
                    "--trace",
                    "site_settings:import",
                    "<",
                    fp.name,
                ],
                environment=environment,
                working_dir=DISCOURSE_PATH,
                user=CONTAINER_APP_USERNAME,
            )
            process.wait_output()
    except ExecError as cmd_err:
        logger.exception("Task site_settings:import failed with code %d.", cmd_err.exit_code)
        raise


def enable_plugins(environment: typing.Dict[str, str], container, plugins: typing.List[str]):
    """Enable discourse plugins."""
    site_settings_config: typing.Dict[str, str] = {plugin: "true" for plugin in plugins}
    update_site_settings(container, environment, site_settings_config)


def disable_plugins(environment: typing.Dict[str, str], container, plugins: typing.List[str]):
    """Disable discourse plugins."""
    site_settings_config: typing.Dict[str, str] = {plugin: "false" for plugin in plugins}
    update_site_settings(container, environment, site_settings_config)
