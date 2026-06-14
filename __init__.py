# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****


bl_info = {
    "name": "Mixamo Rig Kai",
    "author": "Original Author: BeyondDev (Tyler Walker); Kai Maintainer: Gonsaku",
    "version": (0, 3, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Mixamo > Control Rig",
    "description": "Generate a flexible control rig from a Mixamo or reference-mapped humanoid skeleton",
    "category": "Animation",
    "doc_url": "https://github.com/SILL-BILL/mixamo-rig-kai",
    "tracker_url": "https://github.com/SILL-BILL/mixamo-rig-kai/issues",
}


if "bpy" in locals():
    import importlib

    if "mixamo_rig_prefs" in locals():
        importlib.reload(mixamo_rig_prefs)  # noqa: F821
    if "mixamo_rig" in locals():
        importlib.reload(mixamo_rig)  # noqa: F821
    if "kai_reference_template" in locals():
        importlib.reload(kai_reference_template)  # noqa: F821
    if "mixamo_rig_functions" in locals():
        importlib.reload(mixamo_rig_functions)  # noqa: F821
    if "utils" in locals():
        importlib.reload(utils)  # noqa: F821


import bpy  # noqa: F401

from . import (  # noqa: F401
    kai_reference_template,
    mixamo_rig,
    mixamo_rig_functions,
    mixamo_rig_prefs,
    utils,
)


def register():
    mixamo_rig_prefs.register()
    mixamo_rig.register()
    mixamo_rig_functions.register()


def unregister():
    mixamo_rig_prefs.unregister()
    mixamo_rig.unregister()
    mixamo_rig_functions.unregister()


if __name__ == "__main__":
    register()
