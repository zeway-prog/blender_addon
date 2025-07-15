'''
Copyright (C) 2020 Fynn Braren
fynn.braren@posteo.de

Created by Fynn Braren

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import bpy
from bpy.props import IntProperty


from . import auto_load
from .landmarks.landmarks_utils import unlock_3d_view

bl_info = {
    'name': 'FACEIT',
    'author': 'Fynn Braren',
    'description': 'More free stuff for Blender: https://t.me/BlenderUniverse',
    'blender': (2, 80, 0),
    'version': (2, 3, 43),
    'location': 'View3D',
    'warning': '',
    'doc_url': "https://faceit-doc.readthedocs.io/en/latest/",
    'tracker_url': "https://faceit-doc.readthedocs.io/en/latest/support/",
    'category': 'Animation'
}


def update_use_vertex_size_scaling(self, context):
    if self.use_vertex_size_scaling:
        lm_obj = context.scene.objects.get("facial_landmarks")
        if lm_obj:
            if not (lm_obj.hide_get() or lm_obj.hide_viewport):
                context.preferences.themes[0].view_3d.vertex_size = self.landmarks_vertex_size
    else:
        context.preferences.themes[0].view_3d.vertex_size = self.default_vertex_size


def update_auto_lock_3d_view(self, context):
    if not self.auto_lock_3d_view:
        unlock_3d_view()


class FaceitPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    web_links: bpy.props.BoolProperty(
        name='Show Web Links',
        description='Display Links to the Documentation in the Faceit UI',
        default=True,
    )

    use_vertex_size_scaling: bpy.props.BoolProperty(
        name='Landmark Vertex Scaling',
        description='The vertex size will be scaled according to the Landmark Vertex Size during landmark editing. The value will be reset to the Default Size, after applying or resetting the landmarks',
        default=True,
        update=update_use_vertex_size_scaling
    )
    default_vertex_size: bpy.props.IntProperty(
        name="Default Vertex Size",
        description="Vertex Size in Theme Settings (3D view). Set your preferred vertex size.",
        default=3,
        min=1,
        max=10,
        subtype='PIXEL',
        update=update_use_vertex_size_scaling
    )

    landmarks_vertex_size: bpy.props.IntProperty(
        name="Landmarks Vertex Size",
        description="Vertex Size in Theme Settings (3D view). Set your preferred vertex size.",
        default=8,
        min=1,
        max=10,
        subtype='PIXEL',
        update=update_use_vertex_size_scaling
    )
    auto_lock_3d_view: bpy.props.BoolProperty(
        name="Auto Lock 3D View",
        description="Automatically lock the 3D view during Landmarks placement",
        default=True,
        update=update_auto_lock_3d_view
    )
    dynamic_shape_key_ranges: bpy.props.BoolProperty(
        name="Dynamic Shape Key Ranges",
        description="Automatically adjust the slider_min/max ranges of shape keys to the animation data",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.grid_flow(columns=2, align=False)
        col_left = col.column(align=True)
        row = col_left.row(align=True)
        row.label(text="General Settings")
        row = col_left.row(align=True)
        row.prop(self, 'web_links', icon='QUESTION')  # INFO
        row = col_left.row(align=True)
        row.label(text="Animation Settings")
        row = col_left.row(align=True)
        row.prop(self, "dynamic_shape_key_ranges", icon='SHAPEKEY_DATA')

        col_right = col.column(align=True)
        # col_right.use_property_split = True
        # col_right.use_property_decorate = False
        row = col_right.row(align=True)
        row.label(text="Landmark Settings")
        row = col_right.row(align=True)
        row.prop(self, "use_vertex_size_scaling", icon='PROP_OFF')
        if self.use_vertex_size_scaling:
            row = col_right.row(align=True)
            row.prop(self, "default_vertex_size")
            row = col_right.row(align=True)
            row.prop(self, "landmarks_vertex_size")
        col.use_property_split = False
        col_right.separator()
        row = col_right.row()
        row.prop(self, "auto_lock_3d_view", icon='RESTRICT_VIEW_ON')


def cleanse_modules():
    """search for your plugin modules in blender python sys.modules and remove them"""

    import sys

    all_modules = sys.modules
    all_modules = dict(sorted(all_modules.items(), key=lambda x: x[0]))  # sort them

    for k, v in all_modules.items():
        if k.startswith("faceit"):
            if "auto_load" in k:
                continue
            del sys.modules[k]

    return None


auto_load.init()


def register():
    bpy.utils.register_class(FaceitPreferences)
    auto_load.register()

    def get_version(self):
        return bl_info['version'][0]

    bpy.types.Scene.faceit_version = IntProperty(
        name='Faceit Version',
        default=1,
        options=set(),
        get=get_version,
    )


def unregister():
    bpy.utils.unregister_class(FaceitPreferences)
    auto_load.unregister()
    cleanse_modules()
    del bpy.types.Scene.faceit_version
