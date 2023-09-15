# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""helpers for the unit test."""

import contextlib
import typing
import unittest.mock

import ops


@contextlib.contextmanager
def patch_exec(fail: bool = False) -> typing.Generator[unittest.mock.Mock, None, None]:
    """Patch the ops.model.Container.exec method.

    When fail argument is true, the execution will fail.

    Yields:
        Mock for the exec method.
    """
    exec_process_mock = unittest.mock.MagicMock()
    if not fail:
        exec_process_mock.wait_output = unittest.mock.MagicMock(return_value=("", ""))
    else:
        exec_process_mock.wait_output = unittest.mock.Mock()
        exec_process_mock.wait_output.side_effect = ops.pebble.ExecError([], 1, "", "")
    exec_function_mock = unittest.mock.MagicMock(return_value=exec_process_mock)
    with unittest.mock.patch.multiple(ops.model.Container, exec=exec_function_mock):
        yield exec_function_mock
