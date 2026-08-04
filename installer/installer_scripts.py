"""The command text the installer asks Windows to run, and how to read it back.

Separate from installer_logic because this is not a decision: it is the exact
string handed to PowerShell or matched against tasklist output. Building it
here keeps it testable character by character while the module that runs it
(installer_ops.py) stays a thin shell-out. Nothing here imports from the
``fulcrum`` package and nothing here has a side effect.

British spelling is used in comments. No em dashes appear anywhere.
"""

from __future__ import annotations

from pathlib import Path

from installer_logic import EXE_NAME, SHORTCUT_ICON_FILE_NAME

# Deferred delete (when the uninstaller lives inside the dir it must remove).
_DEFERRED_DELETE_ATTEMPTS = 30
_DEFERRED_DELETE_INTERVAL_MS = 500


def shortcut_command(exe_path: Path, link: Path) -> str:
    """Return the PowerShell that writes a shortcut to the installed exe."""
    icon = exe_path.parent / SHORTCUT_ICON_FILE_NAME
    icon_clause = f"$s.IconLocation = '{icon}'; " if icon.exists() else ""
    return (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('"
        f"{link}'); $s.TargetPath = '{exe_path}'; "
        f"$s.WorkingDirectory = '{exe_path.parent}'; "
        f"{icon_clause}$s.Save()"
    )


def deferred_delete_script(install_dir: Path) -> str:
    """Return the PowerShell that deletes a directory once its lock clears."""
    escaped = str(install_dir).replace("'", "''")
    return (
        f"$d = '{escaped}'; "
        f"for ($i = 0; $i -lt {_DEFERRED_DELETE_ATTEMPTS}; $i++) {{ "
        "if (-not (Test-Path -LiteralPath $d)) { break } "
        "Remove-Item -LiteralPath $d -Recurse -Force "
        "-ErrorAction SilentlyContinue; "
        "if (-not (Test-Path -LiteralPath $d)) { break } "
        f"Start-Sleep -Milliseconds {_DEFERRED_DELETE_INTERVAL_MS} "
        "}"
    )


def process_is_running(tasklist_output: str) -> bool:
    """Return True when the task list names the application executable."""
    return EXE_NAME.lower() in tasklist_output.lower()
