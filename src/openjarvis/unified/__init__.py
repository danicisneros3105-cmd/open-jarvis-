"""Unified runtime: OpenJarvis + OpenClacky + God's Eye View as one product.

OpenJarvis is the host. The two bundled extensions live in ``extensions/``:

* ``extensions/clacky`` — OpenClacky, a hands-on agent that drives the
  terminal, the file system and the user's real Chrome. OpenJarvis delegates
  tasks to it through the ``clacky_task`` tool and shares its model config.
* ``extensions/globe`` — God's Eye View, the live 3D globe. It is embedded in
  the OpenJarvis UI and steered from chat through the ``globe_view`` tool.

:mod:`openjarvis.unified.supervisor` starts and stops both services next to
the OpenJarvis server, and :mod:`openjarvis.unified.model_bridge` translates
the OpenJarvis engine/model settings into OpenClacky's environment so both
agents always use the same brain.
"""

from openjarvis.unified.model_bridge import ModelBridgeError, clacky_env
from openjarvis.unified.paths import extension_dir, state_dir
from openjarvis.unified.supervisor import Supervisor

__all__ = [
    "ModelBridgeError",
    "Supervisor",
    "clacky_env",
    "extension_dir",
    "state_dir",
]
