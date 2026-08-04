"""The installer and the application must agree on where user state lives.

The installer is compiled separately and may not import the app, so the
directory name is written down twice by necessity. That is exactly the
condition under which two values drift, and the drift is silent: the
uninstaller offers to remove the user's settings and saved games, deletes a
directory the app has never written and reports success. This test is the
only thing holding the two literals together, so it asserts against the real
paths both sides compute rather than against a constant either one exports.
"""

from pathlib import Path

import installer_logic as logic

from fulcrum.infrastructure.org_autosave import default_autosave_path
from fulcrum.infrastructure.settings_store import default_settings_path


def test_the_installer_removes_the_directory_the_app_actually_writes():
    home = Path.home()
    target = logic.state_dir(home)
    assert default_autosave_path().parent == target
    assert default_settings_path().parent == target


def test_the_state_directory_is_not_the_install_directory():
    # A state directory inside the install root would be destroyed by every
    # upgrade, since deploy_files clears the target before extracting.
    home = Path.home()
    install = logic.install_target(None, home)
    state = logic.state_dir(home)
    assert state != install
    assert install not in state.parents
