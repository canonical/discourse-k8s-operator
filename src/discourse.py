# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Interface for interactions with discourse."""
import logging
import typing

from ops.pebble import ChangeError, ExecError, ExecProcess

CONTAINER_APP_USERNAME = "_daemon_"
DISCOURSE_PATH = "/srv/discourse/app"

logger = logging.getLogger(__name__)


class UpdateSiteSettingsFailedError(Exception):
    """Exception raised when a charm configuration is found to be invalid.

    Attributes:
        msg: Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


def update_site_settings(
    container, environment: typing.Dict[str, str], settings: typing.Dict[str, str]
):
    """Update discourse site_settings."""
    try:
        # The rake site_settings:import task takes a yaml file as input
        # This code inlines the yaml file to avoid having to
        inline_yaml = "\n".join(f"{setting}: {value}" for setting, value in settings.items())
        update_site_settings_command = (
            f"echo '{inline_yaml}' |"
            f" {DISCOURSE_PATH}/bin/bundle exec rake --trace site_settings:import -"
        )
        process: ExecProcess = container.exec(
            ["/bin/bash", "-c", update_site_settings_command],
            environment=environment,
            working_dir=DISCOURSE_PATH,
            user=CONTAINER_APP_USERNAME,
        )
        stdout, _ = process.wait_output()
        return stdout

    except (ChangeError, TypeError, ExecError) as cmd_err:
        logger.exception("Task site_settings:import failed.")
        raise UpdateSiteSettingsFailedError("Task site_settings:import failed.") from cmd_err


def enable_plugins(environment: typing.Dict[str, str], container, plugins: typing.List[str]):
    """Enable discourse plugins."""
    site_settings_config: typing.Dict[str, str] = {
        f"{plugin}_enabled": "true" for plugin in plugins
    }
    return update_site_settings(container, environment, site_settings_config)


def disable_plugins(environment: typing.Dict[str, str], container, plugins: typing.List[str]):
    """Disable discourse plugins."""
    site_settings_config: typing.Dict[str, str] = {
        f"{plugin}_enabled": "false" for plugin in plugins
    }
    return update_site_settings(container, environment, site_settings_config)
