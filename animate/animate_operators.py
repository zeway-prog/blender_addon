import io
import json
import os
import time
from contextlib import redirect_stdout
import timeit

from mathutils import Quaternion, kdtree, Euler, Matrix, Vector
import bpy
import numpy as np
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, StringProperty)
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector


from ..properties.mocap_scene_properties import shapes_action_poll
from ..properties.expression_scene_properties import PROCEDURAL_EXPRESSION_ITEMS

from ..core.pose_utils import reset_pb, reset_pose
from ..core.retarget_list_utils import get_all_set_target_shapes
from ..core import faceit_data as fdata
from ..core import faceit_utils as futils
from ..core import fc_dr_utils
from ..core import shape_key_utils as sk_utils
from ..core.detection_manager import get_expression_name_double_entries
from ..shape_keys.corrective_shape_keys_utils import (
    CORRECTIVE_SK_ACTION_NAME, clear_all_corrective_shape_keys,
    reevaluate_corrective_shape_keys, remove_corrective_shape_key)
from . import animate_utils as a_utils


mirror_sides_dict_L = {
    'left': 'right',
    'Left': 'Right',
    'LEFT': 'RIGHT',
}
mirror_sides_end_L = {
    'L': 'R',
    '_l': '_r',
}

mirror_sides_dict_R = {
    'right': 'left',
    'Right': 'Left',
    'RIGHT': 'LEFT',
}
mirror_sides_end_R = {
    'R': 'L',
    '_r': '_l',
}


def get_side(expression_name) -> str:
    '''Return the side L/N/R for the given expression name'''
    if any(
            [x in expression_name for x in mirror_sides_dict_L]) or any(
            [expression_name.endswith(x) for x in mirror_sides_end_L]):
        return 'L'
    elif any(
            [x in expression_name for x in mirror_sides_dict_R]) or any(
            [expression_name.endswith(x) for x in mirror_sides_end_R]):
        return 'R'
    else:
        return 'N'


def poll_side_in_expression_name(side, expression_name) -> bool:
    '''Check if the correct side is in the expression name'''
    if side == 'L':
        return any(
            [x in expression_name for x in mirror_sides_dict_L]) or any(
            [expression_name.endswith(x) for x in mirror_sides_end_L])
    if side == "R":
        return any(
            [x in expression_name for x in mirror_sides_dict_R]) or any(
            [expression_name.endswith(x) for x in mirror_sides_end_R])
    return False


def get_mirror_name(side, expression_name):
    '''Return the mirror name for the given expression name and side.'''

    if side == "L":
        for key, value in mirror_sides_dict_L.items():
            if key in expression_name:
                return expression_name.replace(key, value)
        for key, value in mirror_sides_end_L.items():
            if expression_name.endswith(key):
                return expression_name.replace(key, value)

    if side == "R":
        for key, value in mirror_sides_dict_R.items():
            if key in expression_name:
                return expression_name.replace(key, value)
        for key, value in mirror_sides_end_R.items():
            if expression_name.endswith(key):
                return expression_name.replace(key, value)
    return ''


def check_expression_name_valid(self, context) -> None:
    '''Update function that checks for a mirror key.'''
    self.expression_sk_exists = self.expression_name in sk_utils.get_shape_key_names_from_objects()
    self.expression_item_exists = self.expression_name in context.scene.faceit_expression_list
    if self.custom_shape:
        self.side = get_side(self.expression_name)
        if poll_side_in_expression_name(self.side, self.expression_name):
            self.auto_mirror = True
            self.side_suffix_found = True


def check_expression_valid(self, context) -> None:
    '''Update function that checks for a mirror key.'''
    self.expression_sk_exists = self.expression_name in sk_utils.get_shape_key_names_from_objects()
    self.expression_item_exists = self.expression_name in context.scene.faceit_expression_list

    # if poll_side_in_expression_name(self.side, self.expression_name):
    if self.custom_shape:
        self.auto_mirror = self.side_suffix_found = (get_side(self.expression_name) == self.side)


def update_procedural_eyeblinks(self, context) -> None:
    '''Set procedural eyeblinks enum property if set by user'''
    self.procedural = 'EYEBLINKS' if self.procedural_eyeblinks else 'NONE'


class FACEIT_OT_AddExpressionItem(bpy.types.Operator):
    '''Add a new Expression to the expression list and action'''
    bl_idname = "faceit.add_expression_item"
    bl_label = "Add Expression"
    bl_options = {'UNDO', 'INTERNAL'}

    expression_name: StringProperty(
        name="Expression Name",
        default="Expression",
        options={'SKIP_SAVE'},
        update=check_expression_name_valid
    )

    new_exp_index: IntProperty(
        name="Index",
        default=-1,
        options={'SKIP_SAVE'},
    )

    expression_sk_exists: BoolProperty(
        name="Index",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    expression_item_exists: BoolProperty(
        name="Index",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    mirror_name_overwrite: StringProperty(
        name="Mirror Expression Name",
        default="",
        description="force side L/R/N",
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    side: EnumProperty(
        name="Expression Side",
        items=(
            ('L', 'Left', 'Expression affects only left side of the face. (Can create a mirror expression)'),
            ('N', 'All', 'Expression affects the whole face. (Left and right side bones are animated)'),
            ('R', 'Right', 'Expression affects only right side of the face. (Can create a mirror expression)'),
        ),
        default='N',
        update=check_expression_valid
    )

    side_suffix_found: BoolProperty(
        name="Side Suffix Found",
        default=False,
        options={'SKIP_SAVE'}
    )

    custom_shape: BoolProperty(
        name="Single Custom Shape",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    auto_mirror: BoolProperty(
        name="Create Mirror Expression",
        default=False,
        options={'SKIP_SAVE'},
    )
    procedural_eyeblinks: BoolProperty(
        name="Procedural Eye Blinks",
        description="Automatically animate eyeblinks for this expression",
        default=False,
        options={'SKIP_SAVE'},
        update=update_procedural_eyeblinks
    )

    procedural: EnumProperty(
        name="Procedural Expression",
        items=PROCEDURAL_EXPRESSION_ITEMS,
        default='NONE',
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    is_new_rigify_rig: BoolProperty(
        name="Is New Rigify Rig",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):

        self.expression_item_exists = self.expression_name in context.scene.faceit_expression_list
        self.expression_sk_exists = self.expression_name in sk_utils.get_shape_key_names_from_objects()
        rig = futils.get_faceit_armature()
        if not futils.is_faceit_original_armature(rig):
            if "lip_end.L.001" in rig.pose.bones:
                self.is_new_rigify_rig = True
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "expression_name")
        if self.expression_sk_exists:
            layout.alert = True
            row = layout.row()
            row.label(text="WARNING: Expression Name already in Shape Keys")
        if self.expression_item_exists:
            layout.alert = True
            row = layout.row()
            row.label(text="WARNING: Expression Name already in List.")
        row = layout.row()
        row.prop(self, "side", expand=True, icon='MOD_MIRROR')

        if self.side == 'N':
            box = layout.box()
            row = box.row(align=True)
            row.label(text="The expression can affect both sides.")

        else:
            if poll_side_in_expression_name(self.side, self.expression_name):
                row = layout.row()
                row.prop(self, "auto_mirror", text="Generate Mirror Expression", icon="MOD_MIRROR")
            if not self.side_suffix_found:
                box = layout.box()
                row = box.row(align=True)
                side_suffix = "Left, L, _L or _l" if self.side == 'L' else "Right, R, _R or _r"
                row.label(text="Please add a suffix to the expression name:")
                row = box.row(align=True)
                row.label(text=f"{self.expression_name} + {side_suffix}")
            else:
                row = layout.row()
                row.prop(self, "procedural_eyeblinks", text="Is EyeBlink")

    def execute(self, context):
        scene = context.scene
        auto_key = scene.tool_settings.use_keyframe_insert_auto
        scene.tool_settings.use_keyframe_insert_auto = False

        expression_list = scene.faceit_expression_list

        shape_action = bpy.data.actions.get("faceit_shape_action")
        ow_action = bpy.data.actions.get("overwrite_shape_action")

        if self.new_exp_index == -1:
            index = len(expression_list)

        frame = int(index + 1) * 10

        expression_name_final = get_expression_name_double_entries(self.expression_name, expression_list)

        # --------------------- Create an Expression Item -----------------------
        item = expression_list.add()
        item.name = expression_name_final
        item.frame = frame
        item.side = self.side
        item.procedural = self.procedural
        if self.mirror_name_overwrite:
            item.mirror_name = self.mirror_name_overwrite

        # --------------------- Custom Expression --------------------------------
        if self.custom_shape:

            if not poll_side_in_expression_name(self.side, self.expression_name):
                self.side = 'N'
            if not item.mirror_name:
                item.mirror_name = get_mirror_name(self.side, expression_name_final)

            if not shape_action:
                shape_action = bpy.data.actions.new("faceit_shape_action")
            if not ow_action:
                ow_action = bpy.data.actions.new("overwrite_shape_action")

            rig = futils.get_faceit_armature()

            if not rig.animation_data:
                rig.animation_data_create()

            for b_item in rig.data.faceit_control_bones:
                b_name = b_item.name
                pb = rig.pose.bones.get(b_name)
                if pb is None:
                    continue
                base_dp = f"pose.bones[\"{b_name}\"]."
                rotation_mode = "rotation_" + a_utils.get_rotation_mode(pb).lower()
                data_paths = [base_dp + "location", base_dp + "scale", base_dp + rotation_mode]
                for dp in data_paths:
                    for i in range(3):
                        fc_dr_utils.get_fcurve_from_bpy_struct(
                            ow_action.fcurves, dp=dp, array_index=i, replace=False)

            if ow_action:
                rig.animation_data.action = ow_action
                a_utils.add_expression_keyframes(rig, frame)

            # Add procedural expression
            try:
                if self.procedural != 'NONE':
                    bpy.ops.faceit.procedural_eye_blinks(
                        side=self.side,
                        anim_mode='ADD' if self.side == 'N' else 'REPLACE',
                        is_new_rigify_rig=self.is_new_rigify_rig
                    )
            except RuntimeError:
                pass

            if self.auto_mirror and self.side != 'N':
                mirror_side = 'R' if self.side == 'L' else 'L'
                bpy.ops.faceit.add_expression_item(
                    'EXEC_DEFAULT',
                    expression_name=item.mirror_name,
                    custom_shape=True,
                    side=mirror_side,
                    procedural=self.procedural,
                    is_new_rigify_rig=self.is_new_rigify_rig,
                )

            scene.faceit_expression_list_index = index

        else:
            try:
                if self.procedural == 'EYEBLINKS':
                    bpy.ops.faceit.procedural_eye_blinks(
                        side=self.side,
                        anim_mode='ADD' if self.side == 'N' else 'REPLACE',
                        is_new_rigify_rig=self.is_new_rigify_rig
                    )
            except RuntimeError:
                pass

        scene.tool_settings.use_keyframe_insert_auto = auto_key
        if ow_action:
            scene.frame_start, scene.frame_end = (int(x) for x in futils.get_action_frame_range(ow_action))

        return {'FINISHED'}


class FACEIT_OT_ChangeExpressionSide(bpy.types.Operator):
    '''Change the expressions side variable. '''
    bl_idname = "faceit.change_expression_side"
    bl_label = "Edit Side"
    bl_options = {'UNDO', 'INTERNAL'}


class FACEIT_OT_MirrorCopy(bpy.types.Operator):
    '''Copy an expression and make them mirrored expressions. Only works for expressions assigned to L/R'''
    bl_idname = "faceit.mirror_copy_expression"
    bl_label = "Mirror Copy Expression"
    bl_options = {'UNDO', 'INTERNAL'}

    expression_to_mirror: StringProperty(
        name="Expression to Mirror",
        default="",
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        return bool(context.scene.faceit_expression_list)

    def execute(self, context):
        if not self.expression_to_mirror:
            self.report({'ERROR'}, "No expression specified to mirror")
            return {'CANCELLED'}
        
        # Pour l'instant, on fait juste un log - l'implémentation complète nécessiterait 
        # plus de logique pour créer réellement l'expression miroir
        self.report({'INFO'}, f"Mirror operation requested for: {self.expression_to_mirror}")
        print(f"FaceIt: Mirror copy requested for expression '{self.expression_to_mirror}'")
        
        # TODO: Implémenter la logique de création d'expression miroir
        return {'FINISHED'}


class FACEIT_OT_EmptyExpressionsFromShapeKeys(bpy.types.Operator):
    '''Copy an expression and make them mirrored expressions. Only works for expressions assigned to L/R'''
    bl_idname = "faceit.empty_expressions_from_shape_keys"
    bl_label = "Copy Empty Expression"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):

        obj = context.object
        if not obj:
            self.report({'ERROR'}, "You need to select an object with shape keys.")
            return {'CANCELLED'}
        if not sk_utils.has_shape_keys(obj):
            self.report({"ERROR"}, f"Object {obj.name} has no shape keys.")
            return {"CANCELLED"}

        for sk in obj.data.shape_keys.key_blocks:
            if sk.name == 'Basis':
                continue
            expression_name = sk.name  # [len('m_head_mid_'):]
            side = get_side(expression_name)
            bpy.ops.faceit.add_expression_item(
                'EXEC_DEFAULT',
                expression_name=expression_name,
                custom_shape=True,
                side=side,
            )
        return {'FINISHED'}


class FACEIT_OT_MoveExpressionItem(bpy.types.Operator):
    '''Move a specific Expression Item index in the list. Also effects the expression actions '''
    bl_idname = "faceit.move_expression_item"
    bl_label = "Move"
    bl_options = {'UNDO', 'INTERNAL'}

    # the name of the facial part
    direction: bpy.props.EnumProperty(
        items=(
            ('UP', 'Up', ''),
            ('DOWN', 'Down', ''),
        ),
        options={'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        idx = context.scene.faceit_expression_list_index
        expression_list = context.scene.faceit_expression_list

        # if idx > 0 and idx <= len(context.scene.faceit_expression_list):
        #     return True
        return expression_list and idx >= 0 and idx < len(expression_list)

    def move_index(self, context, flist, index):
        '''Move the item at index'''
        list_length = len(flist) - 1
        new_index = index + (-1 if self.direction == 'UP' else 1)
        context.scene.faceit_expression_list_index = max(0, min(new_index, list_length))

    def execute(self, context):
        scene = context.scene
        index = scene.faceit_expression_list_index
        expression_list = scene.faceit_expression_list
        expression_item = expression_list[index]

        add_index = -1 if self.direction == 'UP' else 1
        new_index = index + add_index
        add_frame = add_index * 10

        if new_index == len(expression_list) or new_index == -1:
            return {'CANCELLED'}
            # self.report({'ERROR'},)

        new_index_item = expression_list[new_index]

        ow_action = bpy.data.actions.get("overwrite_shape_action")
        sh_action = bpy.data.actions.get("faceit_shape_action")
        cc_action = bpy.data.actions.get(CORRECTIVE_SK_ACTION_NAME)

        # original frame
        expression_frame = expression_item.frame
        new_index_frame = new_index_item.frame

        actions = [ow_action, sh_action]

        for action in actions:
            if action:
                for curve in action.fcurves:
                    for key in curve.keyframe_points:
                        if key.co[0] == new_index_frame:
                            key.co[0] -= add_frame / 2
                    for key in curve.keyframe_points:
                        if key.co[0] == expression_frame:
                            key.co[0] += add_frame
                    for key in curve.keyframe_points:
                        if key.co[0] == new_index_frame - add_frame / 2:
                            key.co[0] -= add_frame / 2

                for curve in action.fcurves:
                    curve.update()
        if cc_action:
            exp_fc = cc_action.fcurves.find(f"key_blocks[\"faceit_cc_{expression_item.name}\"].value")
            if exp_fc:
                for key in exp_fc.keyframe_points:
                    key.co[0] += add_frame
                exp_fc.update()

            new_index_fc = cc_action.fcurves.find(f"key_blocks[\"faceit_cc_{new_index_item.name}\"].value")
            if new_index_fc:
                for key in new_index_fc.keyframe_points:
                    key.co[0] -= add_frame
                new_index_fc.update()

        expression_item.frame = new_index_frame
        new_index_item.frame = expression_frame

        expression_list.move(new_index, index)
        self.move_index(context, expression_list, index)
        return {'FINISHED'}


class FACEIT_OT_RegisterControlBones(bpy.types.Operator):
    '''Register Control Bones for the faceit expressions. The bones are mainly used to determine which bones should be keyframed when creating expressions. (zero keyframes inbetween expressions are important for correct bake results)'''
    bl_idname = "faceit.register_control_bones"
    bl_label = "Register Control Bones"
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if futils.get_faceit_armature() and context.scene.faceit_armature_type == 'ANY':
            obj = context.object
            if obj and obj.type == 'ARMATURE':
                if context.mode == 'POSE' and context.selected_pose_bones:
                    return True

    def execute(self, context):
        added_any = False
        rig = futils.get_faceit_armature()
        for pb in context.selected_pose_bones:
            item = rig.data.faceit_control_bones.get(pb.name)
            if item is None:
                item = rig.data.faceit_control_bones.add()
                item.name = pb.name
            added_any = True
        if added_any:
            self.report({'INFO'}, "Registered control bones for creating expressions.")
        return {'FINISHED'}


class FACEIT_OT_ClearControlBones(bpy.types.Operator):
    '''Clear the list of control bones on the active faceit rig'''
    bl_idname = "faceit.clear_control_bones"
    bl_label = "Clear Control Bones"
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        rig = futils.get_faceit_armature()
        if rig and context.scene.faceit_armature_type == 'ANY':
            if rig.data.faceit_control_bones:
                return True

    def execute(self, context):
        rig = futils.get_faceit_armature()
        rig.data.faceit_control_bones.clear()
        self.report({'INFO'}, "Cleared control bones.")
        return {'FINISHED'}


class FACEIT_OT_SelectControlBones(bpy.types.Operator):
    bl_idname = "faceit.select_control_bones"
    bl_label = "Select Control Bones"
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        rig = futils.get_faceit_armature()
        if rig and context.scene.faceit_armature_type == 'ANY':
            if rig != context.object:
                return False
            if futils.get_hide_obj(rig):
                return False
            if rig.data.faceit_control_bones:
                return True

    def execute(self, context):
        rig = futils.get_faceit_armature()
        if rig.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        for item in rig.data.faceit_control_bones:
            pb = rig.pose.bones.get(item.name)
            if pb:
                pb.bone.select = True
        return {'FINISHED'}


class FACEIT_OT_UpdateControlBones(bpy.types.Operator):
    '''Update the control bone list based on the animated bones.'''
    bl_idname = "faceit.update_control_bones"
    bl_label = "Update Control Bones From Action"
    bl_options = {'UNDO', 'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.scene.faceit_expression_list

    def execute(self, context):
        rig = futils.get_faceit_armature()
        ow_action = bpy.data.actions.get('overwrite_shape_action')
        if not ow_action:
            self.report({'WARNING', "Can't find the epxression action."})
        bone_names = set()
        for fc in ow_action.fcurves:
            # get the bone name
            # TODO: only for non default values, zero frames should be ignored.
            bone_name = fc.data_path.split('"')[1]
            bone_names.add(bone_name)
        for bone_name in bone_names:
            if bone_name not in rig.data.faceit_control_bones:
                item = rig.data.faceit_control_bones.add()
                item.name = bone_name
        return {'FINISHED'}


class FACEIT_OT_AppendActionToFaceitRig(bpy.types.Operator):
    ''' Load a compatible Faceit Expression Action to the Faceit Armature Object. Creates two actions (faceit_shape_action, overwrite_shape_action) '''
    bl_idname = "faceit.append_action_to_faceit_rig"
    bl_label = "Load Faceit Expressions"
    bl_options = {'UNDO', 'INTERNAL'}

    expressions_type: EnumProperty(
        name='Expressions',
        items=(('ARKIT', "ARKit", "The 52 ARKit Expressions that are used in all iOS motion capture apps"),
               ('A2F', "Audio2Face", "The 46 expressions that are used in Nvidias Audio2Face app by default."),
               ('TONGUE', "Tongue", "12 Tongue Expressions that can add realism to speech animation"),
               ('PHONEMES', "Phonemes", "Phoneme Expressions"),
               ),
        default='ARKIT')
    expression_presets = {
        'ARKIT': "arkit_expressions.face",
        'TONGUE': "tongue_expressions.face",
        'PHONEMES': "phoneme_expressions.face",
        'A2F': "a2f_46_expressions.face",
    }
    load_custom_path: BoolProperty(
        name="Load Custom Expressions",
        description="Load a custom expression set. (.face)",
        default=False,
        options={'SKIP_SAVE', },
    )
    load_method: EnumProperty(
        name="Load Method",
        items=(
            ('APPEND', "Append", "Append to existing ExpressionsList"),
            ('OVERWRITE', "Overwrite", "Overwrite existing ExpressionsList"),

        ),
        default='APPEND'
    )
    filepath: StringProperty(
        subtype="FILE_PATH",
        default='face'
    )
    filter_glob: StringProperty(
        default="*.face;",
        options={'HIDDEN'},
    )
    scale_method: EnumProperty(
        name='Scale Method',
        items=(
            ('AUTO', "Auto Scale", "Do automatically scale by matching the rig size to the scene"),
            ('OVERWRITE', "Manual Scale", "Manually overwrite scale of the action"),
        ),
        default='AUTO',
    )
    auto_scale_method: EnumProperty(
        name='Auto Scale Method',
        items=(
            ('GLOBAL', "XYZ", "Scale Pose Translations in XYZ (World Space)."),
            ('AVERAGE', "Average", "Scale Poses by an Average factor."),
        ),
        default='GLOBAL',
    )
    auto_scale_anime_eyes: BoolProperty(
        name="Scale For Anime Eyes",
        default=False,
        description="Scale all expressions down for Anime Eyes (flat eyes with pivots that lie inside the skull)",
        options={'SKIP_SAVE', }
    )
    new_action_scale: FloatVectorProperty(
        name="New Scale",
        default=(1.0, 1.0, 1.0),
    )
    auto_scale_eyes: BoolProperty(
        name="Scale Eye Dimensions",
        default=True
    )
    apply_existing_corrective_shape_keys: BoolProperty(
        name="Apply Corrective Shape Keys",
        description="Try to apply the existing corrective shape keys to the new expressions.",
        default=True,
    )
    is_version_one: BoolProperty(
        options={'SKIP_SAVE', },
    )
    custom_expressions_rig_type: EnumProperty(
        name='Rig Type',
        items=(
            ('RIGIFY', "Rigify", "Faceit default Rig (Rigify old)"),
            ('RIGIFY_NEW', "New Rigify", "The new Rigify Face Rig"),
        ),
        default='RIGIFY',
        options={'SKIP_SAVE', },
    )
    convert_animation_to_new_rigify: BoolProperty(
        name="Convert Animation to New Rigify",
        description="Convert the animation to the new Rigify Rig",
        default=False,
        options={'SKIP_SAVE', },
    )
    load_arkit_reference: BoolProperty(
        name="Load ARKit Reference (Experimental)",
        description="Loads and animates a 3D face model with all ARKit shape keys for reference",
        default=False,
        options={'SKIP_SAVE'}
    )

    @ classmethod
    def poll(cls, context):
        if context.mode not in ['POSE', 'OBJECT']:
            return False
        rig = futils.get_faceit_armature()
        if rig:
            if rig.hide_viewport is False:
                return True

    def invoke(self, context, event):
        self.filepath = "faceit_expressions.face"
        self.corr_sk = any([sk_name.startswith("faceit_cc_")
                            for sk_name in sk_utils.get_shape_key_names_from_objects()])
        rig = futils.get_faceit_armature()
        self.rig_type = futils.get_rig_type(rig)
        if self.rig_type == 'RIGIFY_NEW':
            self.is_new_rigify_rig = True
        elif self.rig_type == 'ANY':
            if not self.load_custom_path:
                self.load_empty_expressions = True
                if not rig.data.faceit_control_bones:
                    self.report(
                        {'ERROR'},
                        "You need to register the facial control bones that should be used for the animation of expressions.")
                    return {'CANCELLED'}
        self.first_expression_set = (len(context.scene.faceit_expression_list) <= 0)
        # check if the rig contains eyelid bones
        self.rig_contains_lid_bones = any(['lid.' in bone.name for bone in rig.pose.bones])
        self.auto_scale_anime_eyes = context.scene.faceit_eye_geometry_type == 'FLAT'

        if self.load_custom_path:
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        else:
            # if self.rig_type == 'ANY':
            #     self.report({'ERROR'}, "The Faceit expressions can only be loaded to Rigify face rigs.")
            #     return {'CANCELLED'}
            wm = context.window_manager
            return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if not self.is_version_one:
            if not self.load_custom_path:
                row = layout.row()
                row.prop(self, "expressions_type")
            if not self.first_expression_set:
                row = layout.row()
                row.label(text="Choose Append Method")
                row = layout.row()
                row.prop(self, "load_method", expand=True)
        if self.expressions_type == 'ARKIT':
            row = layout.row()
            row.prop(self, "load_arkit_reference")
        if self.rig_type == 'ANY':
            box = layout.box()
            row = box.row()
            row.label(text="Warning", icon='ERROR')
            row = box.row()
            row.label(text="Not a Rigify face rig.")
            if not self.load_custom_path:
                row = box.row()
                row.label(text="Load empty expressions?")
                return
        row = layout.row()
        row.label(text="Choose Scale Method")
        row = layout.row()
        row.prop(self, "scale_method", expand=True)
        row = layout.row()
        if self.scale_method == 'OVERWRITE':
            row.prop(self, "new_action_scale")
        elif self.scale_method == 'AUTO':
            row.prop(self, "auto_scale_method", expand=True)
        row = layout.row()
        row.prop(self, "auto_scale_eyes", icon='CON_DISTLIMIT')
        if self.corr_sk:
            row = layout.row()
            row.prop(self, "apply_existing_corrective_shape_keys")
        # if context.scene.faceit_eye_pivot_options == 'COPY_PIVOT':
        if context.scene.faceit_eye_geometry_type == 'FLAT':
            row = layout.row()
            row.label(text="Flat Eyes")
            row = layout.row()
            row.prop(self, "auto_scale_anime_eyes", icon='LIGHT_HEMI')
        if self.load_method == 'OVERWRITE' and not self.first_expression_set:
            box = layout.box()
            row = box.row()
            row.label(text="Warning", icon='ERROR')
            row = box.row()
            row.label(text="This will overwrite the existing expressions!")

    def execute(self, context):
        # Initialize variables if not already set (in case execute is called directly)
        if not hasattr(self, 'corr_sk'):
            self.corr_sk = False
        if not hasattr(self, 'first_expression_set'):
            self.first_expression_set = False
        if not hasattr(self, 'is_new_rigify_rig'):
            self.is_new_rigify_rig = False
        if not hasattr(self, 'rig_type'):
            self.rig_type = 'FACEIT'
        if not hasattr(self, 'rig_contains_lid_bones'):
            self.rig_contains_lid_bones = False
        if not hasattr(self, 'load_empty_expressions'):
            self.load_empty_expressions = False
            
        scene = context.scene
        save_frame = scene.frame_current
        state_dict = futils.save_scene_state(context)
        if self.load_custom_path:
            _filename, extension = os.path.splitext(self.filepath)
            if extension != ".face":
                self.report({'ERROR'}, "You need to provide a file of type .face")
                return {'CANCELLED'}
            if not os.path.isfile(self.filepath):
                self.report({'ERROR'}, f"The specified filepath does not exist: {os.path.realpath(self.filepath)}")
                return {'CANCELLED'}
            expressions_type = None
        else:
            expressions_type = self.expressions_type
        expression_list = scene.faceit_expression_list
        warnings = False
        if futils.get_object_mode_from_context_mode(context.mode) != 'OBJECT' and context.object is not None:
            bpy.ops.object.mode_set()
        rig = futils.get_faceit_armature()
        if not rig.animation_data:
            rig.animation_data_create()
        ow_action = bpy.data.actions.get("overwrite_shape_action")
        shape_action = bpy.data.actions.get("faceit_shape_action")
        if self.load_method == 'APPEND':
            if not expression_list:
                self.report(
                    {'INFO'},
                    "Could not append the expressions, because there are no shapes. Using Overwrite method instead")
                self.load_method = 'OVERWRITE'
            if not shape_action or not ow_action:
                self.report(
                    {'INFO'},
                    "Could not append the action, because no Action was found. Using Overwrite method instead")
                self.load_method = 'OVERWRITE'
        if self.load_method == 'OVERWRITE':
            expression_list.clear()
            if shape_action:
                bpy.data.actions.remove(shape_action)
                shape_action = None
            if ow_action:
                bpy.data.actions.remove(ow_action)
                ow_action = None
        # Reset all bone transforms!
        futils.set_active_object(rig.name)
        if bpy.app.version < (4, 0, 0):
            layer_state = rig.data.layers[:]
            # enable all armature layers; needed for armature operators to work properly
            for i in range(len(rig.data.layers)):
                rig.data.layers[i] = True
        else:
            layer_state = [c.is_visible for c in rig.data.collections]
            for c in rig.data.collections:
                c.is_visible = True
        bpy.ops.object.mode_set(mode='POSE')
        # bpy.ops.pose.select_all(action='SELECT')
        # bpy.ops.pose.transforms_clear()
        # ------------------ Read New Expressions Data ------------------------
        # | - Load Expressions Data to temp action
        # | - Keyframes, Rig Dimensions, Rest Pose,
        # ---------------------------------------------------------------------
        new_shape_action = None
        if not self.load_custom_path:
            self.filepath = os.path.join(fdata.get_expression_presets(
                rig_type=self.rig_type), self.expression_presets[expressions_type])
        if not os.path.isfile(self.filepath):
            self.report({'ERROR'}, f"The specified filepath does not exist: {os.path.realpath(self.filepath)}")
            return {'CANCELLED'}
        action_dict = {}
        eye_dimensions = []
        loaded_rig_type = 'FACEIT'
        with open(self.filepath, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                expression_data_loaded = data["expressions"]
                # import_rig_dimensions = data["action_scale"]
                rest_pose = data["rest_pose"]
                action_dict = data["action"]
                eye_dimensions = data.get("eye_dimensions")
                loaded_rig_type = data.get("rig_type", 'FACEIT')
        if loaded_rig_type == 'FACEIT' and self.is_new_rigify_rig:
            print("Converting old FaceIt Rig to new Rigify Rig")
            self.convert_animation_to_new_rigify = True
        new_shape_action = bpy.data.actions.new(name="temp")
        new_expression_count = len(expression_data_loaded.keys())
        zero_frames = set()
        new_frames = []
        for i in range(new_expression_count):
            frame = (i + 1) * 10
            new_frames.append(frame)
            zero_frames.update((frame + 1, frame - 9))
        zero_frames = sorted(list(zero_frames))
        if self.load_empty_expressions:
            if self.load_method == 'OVERWRITE':
                rig.animation_data.action = new_shape_action
                new_shape_action.name = "faceit_shape_action"
            for expression_name, expression_data in expression_data_loaded.items():
                mirror_name = expression_data.get("mirror_name", "")
                side = expression_data.get("side") or "N"
                bpy.ops.faceit.add_expression_item(
                    'EXEC_DEFAULT',
                    expression_name=expression_name,
                    side=side,
                    mirror_name_overwrite=mirror_name,
                )
            if self.load_method == 'OVERWRITE':
                ow_action = a_utils.create_overwrite_animation(rig)
                rig.animation_data.action = ow_action
                ow_action.use_fake_user = True
                new_shape_action.use_fake_user = True
            # Create the zero frames
            bone_filter = [b.name for b in rig.data.faceit_control_bones]
            a_utils.create_default_zero_frames(
                zero_frames=zero_frames,
                action=ow_action,
                rig=rig,
                bone_filter=bone_filter
            )
        else:
            rig.animation_data.action = new_shape_action
            start_time = time.time()
            missing_dps = []
            for dp, data_per_array_index in action_dict.items():
                parsed_data_path = a_utils.parse_pose_bone_data_path(dp)
                bone_name = parsed_data_path["bone_name"]
                prop_name = parsed_data_path["prop_name"]
                custom_prop_name = parsed_data_path["custom_prop_name"]
                if self.convert_animation_to_new_rigify:
                    new_name = fdata.get_rigify_bone_from_old_name(bone_name)
                    dp = dp.replace(bone_name, new_name)
                    bone_name = new_name
                if bone_name not in rig.pose.bones:
                    if self.is_new_rigify_rig:
                        # TODO: this bit should definitely be refactored.
                        if 'lip_end.L' in bone_name:
                            # get the actual bone name independent of the lip subdivs.
                            if bone_name in rig.pose.bones:
                                pass
                            else:
                                bone = next((b for b in rig.pose.bones if b.name.startswith('lip_end.L')), None)
                                dp = dp.replace(bone_name, bone.name)
                                bone_name = bone.name
                        if 'lip_end.R' in bone_name:
                            # get the actual bone name independent of the lip subdivs.
                            if bone_name in rig.pose.bones:
                                pass
                            else:
                                bone = next((b for b in rig.pose.bones if b.name.startswith('lip_end.R')), None)
                                dp = dp.replace(bone_name, bone.name)
                                bone_name = bone.name
                try:
                    rig.path_resolve(dp)
                except ValueError:
                    self.report({'WARNING'}, f"The path {dp} could not be resolved. Skipping the animation curves.")
                    missing_dps.append(dp)
                    continue
                if not custom_prop_name and not prop_name:
                    # could still try to resolve the path and add the keyframes manually.
                    self.report({'WARNING'}, f"{dp} is not a supported path. Skipping the animation curves.")
                    missing_dps.append(dp)
                    continue
                pose_bone = rig.pose.bones.get(bone_name)
                channels = 1
                default = None
                prop = None
                if prop_name:
                    prop = pose_bone.bl_rna.properties.get(prop_name)
                    if getattr(prop, "is_array", False):
                        default = [p for p in prop.default_array]
                        channels = len(default)
                    else:
                        default = [prop.default]
                elif custom_prop_name:
                    custom_prop = pose_bone.id_properties_ui(custom_prop_name)
                    default = custom_prop.as_dict().get("default")
                    if default is not None:
                        if hasattr(default, "__iter__"):
                            channels = len(default)
                        else:
                            default = [default]
                if "rotation" in prop_name:
                    rot_mode_to = a_utils.get_rotation_mode(pose_bone)
                    rotation_data_path_to = a_utils.get_data_path_from_rotation_mode(rot_mode_to)
                    rot_mode_from = a_utils.get_rotation_mode_from_data_path_val(prop_name)
                    # Check if the rotation mode is already the expected rotation mode, nothing needs to be done
                    if rotation_data_path_to != prop_name:
                        if rot_mode_to == 'EULER':
                            new_channels = 3
                        else:
                            new_channels = 4
                        # Replace the data path with the expected rotation mode
                        dp = dp.replace(prop_name, rotation_data_path_to)
                        # Get the number of channels for the old rotation mode and new rotation_mode
                        # Reconstruct full rotation values based on the individual channels in the data array
                        # and convert them to the expected rotation mode
                        # currently the data is stored like this: {i: [(frame, value), (frame, value), ...]}
                        # new format (frames_dict) for rotation mode conversion {frame: {i:[value, value, ...]}}
                        frames_dict = {}
                        for i, frame_value_list in data_per_array_index.items():
                            i = int(i)
                            for frame, value in frame_value_list:
                                if frame not in frames_dict:
                                    frames_dict[frame] = {}
                                frames_dict[frame][i] = value
                        # Convert the rotation values to the expected rotation mode and populate into the data_dict
                        data_per_array_index = {}
                        for frame, value_dict in frames_dict.items():
                            rot_value = []
                            for i in range(channels):
                                val = value_dict.get(i)
                                if val:
                                    rot_value.append(val)
                                else:
                                    # Reconstruct missing values (default value for this channel)
                                    rot_value.append(default[i])
                            rot_value = a_utils.get_value_as_rotation(rot_mode_from, rot_value)  # Euler(rot_value)
                            new_rot_value = a_utils.convert_rotation_values(rot_value, rot_mode_from, rot_mode_to)[:]
                            # Reconstruct the data dict with new rotation mode / values
                            for i, value in enumerate(new_rot_value):
                                i = str(i)
                                if i not in data_per_array_index:
                                    data_per_array_index[i] = []
                                data_per_array_index[i].append([frame, value])
                        channels = new_channels
                        # Reload the prop for the target rotation
                        new_prop_name = a_utils.get_data_path_from_rotation_mode(rot_mode_to)
                        prop = pose_bone.bl_rna.properties.get(new_prop_name)
                        default = [p for p in prop.default_array]
                        channels = len(default)
                # Populate the action with loaded data.
                for i in range(channels):
                    data = data_per_array_index.get(str(i))
                    fc = new_shape_action.fcurves.new(data_path=dp, index=i, action_group=bone_name)
                    # Adding Zero Keyframes for all rest poses inbetween expressions!
                    kf_zero_data = np.array([(f, default[i]) for f in zero_frames])
                    if data:
                        # Load the actual keyframes and merge with zero frames.
                        kf_data = np.vstack((np.array(data), kf_zero_data))
                    else:
                        kf_data = kf_zero_data
                    fc_dr_utils.populate_keyframe_points_from_np_array(fc, kf_data, add=True)
                    for kf in fc.keyframe_points:
                        kf.interpolation = 'LINEAR'
            print(f"Added new Keyframes in {round(time.time() - start_time, 2)}")
            if missing_dps:
                self.report({'WARNING'}, "Some fcurves could not be imported. See console output for more information.")
                warnings = True
            # ------------------------- SCALE ACTION ----------------------------------
            # | - Scale Action to new rig dimensions.
            # | - Eyelid is calculated and scaled separately.
            # -------------------------------------------------------------------------
            if self.rig_type in ('RIGIFY', 'RIGIFY_NEW'):
                skip_lid_bones = {
                    "lid.T.L.003",
                    "lid.T.L.002",
                    "lid.T.L.001",
                    "lid.B.L.001",
                    "lid.B.L.002",
                    "lid.B.L.003",
                    "lid.B.L",
                    "lid.T.L",
                    "lid.T.R.003",
                    "lid.T.R.002",
                    "lid.T.R.001",
                    "lid.B.R.001",
                    "lid.B.R.002",
                    "lid.B.R.003",
                    "lid.B.R",
                    "lid.T.R",
                }
                skip_double_constraint = {
                    "nose.005",
                    "chin.002",
                    "nose.003",
                }
                skip_scale_bones = skip_double_constraint
                if eye_dimensions and self.auto_scale_eyes:
                    skip_scale_bones.update(skip_lid_bones)
                # get control bones on the face only (no eye target controllers)
                skip_dimension_check = {"eye.L", "eye.R", "eyes", "eye_common"}
                facial_control_bones = {pb.name for pb in rig.pose.bones if pb.name in fdata.FACEIT_CTRL_BONES}
            else:
                skip_scale_bones = set()
                skip_dimension_check = set()
                facial_control_bones = {pb.name for pb in rig.pose.bones}
            # Relevant / animated bones for scaling
            # Dimension relevant control bones that are present in rig and in the imported data
            bone_dimensions_check = facial_control_bones.intersection(rest_pose) - skip_dimension_check

            def get_import_rig_dimensions(pose_bones):
                '''Get the dimensions of the imported rest pose data'''
                x_values = []
                y_values = []
                z_values = []
                # Return the bones that are found for comparison!
                # for _, values in rest_pose.items():
                for pb in pose_bones:
                    values = rest_pose.get(pb.name)
                    x_values.append(values[0])
                    y_values.append(values[1])
                    z_values.append(values[2])
                dim_x = max(x_values) - min(x_values)
                dim_y = max(y_values) - min(y_values)
                dim_z = max(z_values) - min(z_values)
                return [dim_x, dim_y, dim_z]

            def get_rig_dimensions(pose_bones):
                '''Get the dimensions for all faceit control bones'''
                x_values = []
                y_values = []
                z_values = []
                for pb in pose_bones:
                    x_values.append(pb.bone.matrix_local.translation[0])
                    y_values.append(pb.bone.matrix_local.translation[1])
                    z_values.append(pb.bone.matrix_local.translation[2])
                dim_x = max(x_values) - min(x_values)
                dim_y = max(y_values) - min(y_values)
                dim_z = max(z_values) - min(z_values)
                return [dim_x, dim_y, dim_z]

            action_scale = [1.0, ] * 3
            scale_bones = [pb for pb in rig.pose.bones if pb.name in (facial_control_bones - skip_scale_bones)]
            # scale_bones = [pb for pb in facial_control_bones if pb.name not in skip_scale_bones]
            if self.scale_method == 'AUTO':
                # get bones present in both current pose and imported pose and compare dimensions
                bone_dimensions_check = [pb for pb in rig.pose.bones if pb.name in bone_dimensions_check]
                if not bone_dimensions_check:
                    self.report({'WARNING'}, "No bones found for scaling the action!")
                else:
                    import_rig_dimensions = get_import_rig_dimensions(bone_dimensions_check)
                    zero_dims = import_rig_dimensions.count(0)
                    if zero_dims:
                        # if any of the dimensions is 0, fill list with average of the other
                        import_rig_dimensions[import_rig_dimensions.index(0)] = sum(
                            import_rig_dimensions) / (3 - zero_dims)
                        self.report(
                            {'WARNING'},
                            f"Automatic Scaling Problem. Found {zero_dims} dimensions with 0. Filled with average of the other dimensions.")
                    rig_dim = get_rig_dimensions(bone_dimensions_check)
                    for i in range(3):
                        action_scale[i] = rig_dim[i] / import_rig_dimensions[i]
                    if not all(x == 1 for x in action_scale):
                        if self.auto_scale_method == 'GLOBAL':
                            a_utils.scale_poses_to_new_dimensions_slow(
                                rig,
                                pose_bones=scale_bones,
                                scale=action_scale,
                                active_action=new_shape_action,
                                frames=new_frames
                            )
                        else:
                            a_utils.scale_action_to_rig(
                                new_shape_action,
                                action_scale,
                                filter_skip=skip_lid_bones,
                                frames=new_frames
                            )
            elif self.scale_method == 'OVERWRITE':
                action_scale = self.new_action_scale
                if not all(x == 1 for x in action_scale):
                    a_utils.scale_poses_to_new_dimensions_slow(
                        rig,
                        pose_bones=scale_bones,
                        scale=action_scale,
                        active_action=new_shape_action,
                        frames=new_frames
                    )
            if self.rig_type in ('RIGIFY', 'RIGIFY_NEW', 'FACEIT'):
                # Scale eyelid expressions to new dimensions!
                if self.rig_contains_lid_bones and eye_dimensions and self.auto_scale_eyes:
                    a_utils.scale_eye_animation(rig, *eye_dimensions, action=new_shape_action)
                if self.auto_scale_anime_eyes:
                    a_utils.scale_eye_look_animation(rig, scale_factor=0.45, action=new_shape_action)
                # check if the expressions are generated with the new rigify rig, if so no need to scale.
                if self.is_new_rigify_rig and self.convert_animation_to_new_rigify:  # and self.convert_to_new_rigify_rig:
                    a_utils.scale_eye_look_animation(rig, scale_factor=0.25, action=new_shape_action)

            # ------------------------ Append the keyframes -------------------------------
            # | - Append the Keyframes
            # | - Activate the Shape Action
            # -------------------------------------------------------------------------
            if self.load_method == 'OVERWRITE':
                shape_action = new_shape_action
                shape_action.name = "faceit_shape_action"
            else:
                # Apply frame offset to the fcurve data and apply to existing shape action
                frame_offset = int(futils.get_action_frame_range(ow_action)[1] - 1)
                for import_fc in new_shape_action.fcurves:
                    kf_data = fc_dr_utils.kf_data_to_numpy_array(import_fc)
                    kf_data[:, 0] += frame_offset
                    dp = import_fc.data_path
                    a_index = import_fc.array_index
                    if shape_action:
                        fc = fc_dr_utils.get_fcurve_from_bpy_struct(shape_action.fcurves, dp=dp, array_index=a_index)
                        fc_dr_utils.populate_keyframe_points_from_np_array(fc, kf_data, add=True)
                    else:
                        self.report({'WARNING'}, "Could not find the Faceit Shape Action. Failed to append")
                        warnings = True
                    if ow_action:
                        fc = fc_dr_utils.get_fcurve_from_bpy_struct(ow_action.fcurves, dp=dp, array_index=a_index)
                        fc_dr_utils.populate_keyframe_points_from_np_array(fc, kf_data, add=True)
                    else:
                        self.report({'WARNING'}, "Could not find the Faceit Overwrite Action. Failed to append")
                        warnings = True
                bpy.data.actions.remove(new_shape_action)
            if self.load_method == 'OVERWRITE':
                ow_action = a_utils.create_overwrite_animation(rig)
            if ow_action:
                rig.animation_data.action = ow_action
                ow_action.use_fake_user = True
            if shape_action:
                shape_action.use_fake_user = True
            # ------------------------ Load Expressions -------------------------------
            # | - Load Expressions Items to list.
            # -------------------------------------------------------------------------
            for expression_name, expression_data in expression_data_loaded.items():
                mirror_name = expression_data.get("mirror_name", "")
                side = expression_data.get("side") or "N"
                procedural = expression_data.get("procedural", 'NONE')
                bpy.ops.faceit.add_expression_item(
                    'EXEC_DEFAULT',
                    expression_name=expression_name,
                    side=side,
                    mirror_name_overwrite=mirror_name,
                    procedural=procedural,
                    is_new_rigify_rig=self.is_new_rigify_rig
                )

            if self.rig_type in ('RIGIFY', 'RIGIFY_NEW', 'FACEIT'):
                try:
                    if expressions_type == 'ARKIT':  # and not self.load_custom_path:
                        bpy.ops.faceit.procedural_mouth_close(
                            'INVOKE_DEFAULT',
                            jaw_open_expression="jawOpen",
                            mouth_close_expression="mouthClose",
                            is_new_rigify_rig=self.is_new_rigify_rig
                        )
                    if expressions_type == 'A2F':  # and not self.load_custom_path:
                        bpy.ops.faceit.procedural_mouth_close(
                            'INVOKE_DEFAULT',
                            jaw_open_expression="jawDrop",
                            mouth_close_expression="jawDropLipTowards",
                            is_new_rigify_rig=self.is_new_rigify_rig
                        )
                except RuntimeError:
                    pass
        if self.load_arkit_reference:
            bpy.ops.faceit.load_arkit_refernce()
        # bpy.ops.faceit.force_zero_frames('EXEC_DEFAULT')
        if bpy.app.version < (4, 0, 0):
            rig.data.layers = layer_state[:]
        else:
            for i, c in enumerate(rig.data.collections):
                c.is_visible = layer_state[i]

        if warnings:
            self.report(
                {'WARNING'},
                "Operator finished with Warnings. Take a look at the console output for more information.")
        else:
            self.report({'INFO'}, "New Expressions.")
        if self.apply_existing_corrective_shape_keys and not (
                self.load_method == 'OVERWRITE' and self.load_empty_expressions):
            reevaluate_corrective_shape_keys(expression_list, futils.get_faceit_objects_list())
        else:
            clear_all_corrective_shape_keys(futils.get_faceit_objects_list(), expression_list=expression_list)
        scene.frame_start, scene.frame_end = (int(x) for x in futils.get_action_frame_range(ow_action))
        futils.restore_scene_state(context, state_dict)
        if self.first_expression_set:
            scene.tool_settings.use_keyframe_insert_auto = True
        scene.frame_current = save_frame
        futils.ui_refresh_all()
        return {'FINISHED'}


class FACEIT_OT_ForceZeroFrames(bpy.types.Operator):
    ''' Adds Zero Keyframes (default values) between the animated expressions! Effects only pose bone properties with default values'''
    bl_idname = "faceit.force_zero_frames"
    bl_label = "Update Zero Frames"
    bl_options = {'UNDO', 'REGISTER'}

    @ classmethod
    def poll(cls, context):
        scene = context.scene
        rig = futils.get_faceit_armature()
        if rig and scene.faceit_expression_list and context.mode in ['OBJECT', 'POSE']:
            if rig.animation_data:
                if rig.animation_data.action:
                    return True
        return False

    def execute(self, context):
        rig = futils.get_faceit_armature()
        zero_frames = set()
        new_frames = []
        for i in range(len(context.scene.faceit_expression_list)):
            frame = (i + 1) * 10
            new_frames.append(frame)
            zero_frames.update((frame + 1, frame - 9))
        # bone_filter = [b.name for b in rig.data.faceit_control_bones]
        a_utils.update_zero_frames(
            zero_frames=zero_frames,
            action=rig.animation_data.action,
            rig=rig,
        )
        futils.ui_refresh_all()
        return {'FINISHED'}


class FACEIT_OT_CleanupUnusedFCurves(bpy.types.Operator):
    '''Removes Fcurves that contain no keyframes or only default values.'''
    bl_idname = "faceit.cleanup_unused_fcurves"
    bl_label = "Cleanup Unsused Fcurves"
    bl_options = {'UNDO', 'REGISTER'}

    @ classmethod
    def poll(cls, context):
        scene = context.scene
        rig = futils.get_faceit_armature()
        if rig and scene.faceit_expression_list and context.mode in ['OBJECT', 'POSE']:
            if rig.animation_data:
                if rig.animation_data.action:
                    return True
        return False

    def execute(self, context):
        rig = futils.get_faceit_armature()
        n_removed = a_utils.cleanup_unused_fcurves(rig, rig.animation_data.action)
        self.report({'INFO'}, f"Removed {n_removed} fcurves from the action {rig.animation_data.action.name}")
        return {'FINISHED'}

# START ####################### VERSION 2 ONLY #######################


class FACEIT_OT_ExportExpressionsToJson(bpy.types.Operator, ExportHelper):
    ''' Export the current Expression file to json format '''
    bl_idname = "faceit.export_expressions"
    bl_label = "Export Expressions"
    bl_options = {'UNDO', 'INTERNAL', 'REGISTER'}

    filepath: StringProperty(
        subtype="FILE_PATH",
        default="faceit_expressions"
    )
    filter_glob: StringProperty(
        default="*.face;",
        options={'HIDDEN'},
    )
    # rig_type: EnumProperty(
    #     items=[
    #         ('RIGIFY', "Rigify", ""),
    #         ('RIGIFY_NEW', "Rigify New", ""),
    #     ],
    #     name="Rig Type",
    #     default='RIGIFY'
    # )
    filename_ext = ".face"
    adjust_scale = True
    # rig_type = 'FACEIT'

    @ classmethod
    def poll(cls, context):
        scene = context.scene
        rig = futils.get_faceit_armature()
        if rig and scene.faceit_expression_list:
            if rig.animation_data:
                if rig.animation_data.action:
                    return True

    def execute(self, context):
        scene = context.scene
        rig = futils.get_faceit_armature()
        # value in 'FACEIT', 'RIGIFY', 'RIGIFY_NEW'
        rig_type = futils.get_rig_type(rig)
        scene = context.scene
        save_frame = scene.frame_current
        auto_key = scene.tool_settings.use_keyframe_insert_auto
        scene.tool_settings.use_keyframe_insert_auto = False
        expression_list = scene.faceit_expression_list
        reset_pose(rig)
        action_scale = list(rig.dimensions.copy())
        data = {}
        data["rig_type"] = rig_type
        data["action_scale"] = list(action_scale)
        if rig_type in ('RIGIFY', 'RIGIFY_NEW'):
            eye_dim_L, eye_dim_R = a_utils.get_eye_dimensions(rig)
            data["eye_dimensions"] = [eye_dim_L, eye_dim_R]
            control_bones = fdata.FACEIT_CTRL_BONES

        else:
            control_bones = [b.name for b in rig.data.faceit_control_bones]
            if not control_bones:
                self.report({'WARNING'}, "Control Bones are not registered. The export results might have the wrong scale.")
        # Store the rest pose for the relevant control bones. Important for matching the scale on import.
        rest_pose_dict = {}
        for b in rig.data.bones:
            if b.name in control_bones:
                rest_pose_dict[b.name] = list(b.matrix_local.translation)
        expression_list_data = {}
        expression_list = scene.faceit_expression_list
        for exp in expression_list:
            expression_options = {
                'mirror_name': exp.mirror_name,
                'side': exp.side,
                'procedural': 'NONE'
            }
            if 'RIGIFY' in rig_type:
                procedural = getattr(exp, "procedural", 'NONE')
                if exp.name in ("eyeBlinkLeft", "eyeBlinkRight") and procedural == 'NONE':
                    procedural = 'EYEBLINKS'
                expression_options['procedural'] = procedural
            expression_list_data[exp.name] = expression_options

        # Export the expression data
        action = rig.animation_data.action
        action_dict = {}
        remove_zero_keyframes = True
        remove_zero_poses = True
        for fc in action.fcurves:
            dp = fc.data_path
            array_index = fc.array_index
            # skip non-control bones
            if rig_type in ('RIGIFY', 'RIGIFY_NEW'):
                if any(x in dp for x in ["DEF-", "MCH-", "ORG-"]):
                    continue
            # Skip constraint animation
            if "influence" in dp:
                continue
            if "mouth_lock" in dp:
                print("skipping mouth lock")
                continue
            kf_data = fc_dr_utils.kf_data_to_numpy_array(fc)
            if remove_zero_poses:
                kf_data = kf_data[np.logical_not(kf_data[:, 0] % 10 != 0)]
            if remove_zero_keyframes:  # Default values
                if "scale" in fc.data_path or "rotation_quaternion" in fc.data_path and array_index == 0:
                    kf_data = kf_data[np.logical_not(kf_data[:, 1] == 1.0)]
                else:
                    # delete zero values
                    kf_data = kf_data[np.logical_not(kf_data[:, 1] == 0.0)]
            kf_anim_data = kf_data.tolist()
            if not kf_anim_data:
                continue
            dp_dict = action_dict.get(dp)
            if dp_dict:
                dp_dict[array_index] = kf_anim_data
            else:
                action_dict[dp] = {array_index: kf_anim_data}

        data["expressions"] = expression_list_data
        data["rest_pose"] = rest_pose_dict
        data["action"] = action_dict
        if not self.filepath.endswith(".face"):
            self.filepath += ".face"
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        scene.frame_current = save_frame
        scene.tool_settings.use_keyframe_insert_auto = auto_key

        return {'FINISHED'}


class FACEIT_OT_ClearFaceitExpressions(bpy.types.Operator):
    '''Clear all Faceit Expressions'''
    bl_idname = "faceit.clear_faceit_expressions"
    bl_label = "Clear Expressions"
    bl_options = {'UNDO', 'INTERNAL'}

    keep_corrective_shape_keys: BoolProperty(
        name="Keep Corrective Shape Keys",
        description="Keep all corrective Shape Keys and try to apply them on a new expression.",
        default=True,
    )

    corr_sk = True

    @ classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        self.corr_sk = any([sk_name.startswith("faceit_cc_")
                           for sk_name in sk_utils.get_shape_key_names_from_objects()])

        if self.corr_sk:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        else:
            return self.execute(context)

    def execute(self, context):
        scene = context.scene
        scene.faceit_expression_list.clear()
        scene.faceit_expression_list_index = -1
        shape_action = bpy.data.actions.get("faceit_shape_action")
        ow_action = bpy.data.actions.get("overwrite_shape_action")
        if shape_action:
            bpy.data.actions.remove(shape_action)
        if ow_action:
            bpy.data.actions.remove(ow_action)

        rig = futils.get_faceit_armature()

        if rig:
            if rig.animation_data:
                rig.animation_data.action = None

            for b in rig.pose.bones:
                reset_pb(b)
        if self.corr_sk:
            faceit_objects = futils.get_faceit_objects_list()

            for obj in faceit_objects:

                if sk_utils.has_shape_keys(obj):
                    for sk in obj.data.shape_keys.key_blocks:
                        if sk.name.startswith("faceit_cc_"):
                            # mute corrective shapes!
                            if self.keep_corrective_shape_keys:
                                sk.mute = True
                                scene.faceit_corrective_sk_restorable = True
                            else:
                                obj.shape_key_remove(sk)
                                scene.faceit_corrective_sk_restorable = False

                    if obj.data.shape_keys.animation_data:
                        a = obj.data.shape_keys.animation_data.action
                        if a:
                            if a.name == CORRECTIVE_SK_ACTION_NAME:
                                obj.data.shape_keys.animation_data.action = None

                    if len(obj.data.shape_keys.key_blocks) == 1:
                        obj.shape_key_clear()
        return {'FINISHED'}


class FACEIT_OT_RemoveExpressionItem(bpy.types.Operator):
    '''Remove the selected Character Geometry from Registration.'''
    bl_idname = "faceit.remove_expression_item"
    bl_label = "Remove Expression"
    bl_options = {'UNDO', 'INTERNAL'}

    remove_item: bpy.props.StringProperty(
        default="",
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @ classmethod
    def poll(cls, context):
        idx = context.scene.faceit_expression_list_index

        if idx >= 0 and idx < len(context.scene.faceit_expression_list):
            return True

    def execute(self, context):

        scene = context.scene
        auto_key = scene.tool_settings.use_keyframe_insert_auto
        scene.tool_settings.use_keyframe_insert_auto = False

        expression_list = scene.faceit_expression_list
        expression_list_index = scene.faceit_expression_list_index

        ow_action = bpy.data.actions.get("overwrite_shape_action")
        sh_action = bpy.data.actions.get("faceit_shape_action")

        if len(expression_list) <= 1:
            bpy.ops.faceit.clear_faceit_expressions()
            scene.frame_start, scene.frame_end = 1, 250
            return {'FINISHED'}

        def _remove_faceit_item(item):

            item_index = expression_list.find(item.name)

            frame = item.frame

            actions = [ow_action, sh_action]
            for action in actions:
                if action:
                    for curve in action.fcurves:
                        for key in curve.keyframe_points:
                            if key.co[0] == frame:
                                curve.keyframe_points.remove(key, fast=True)
                    for curve in action.fcurves:
                        for key in curve.keyframe_points:
                            if key.co[0] > frame:
                                key.co[0] -= 10

            cc_action = bpy.data.actions.get(CORRECTIVE_SK_ACTION_NAME)
            if cc_action:
                for curve in cc_action.fcurves:
                    for key in curve.keyframe_points:
                        if key.co[0] == frame:
                            curve.keyframe_points.remove(key, fast=True)
                for curve in cc_action.fcurves:
                    for key in curve.keyframe_points:
                        if key.co[0] > frame:
                            key.co[0] -= 10

            expression_list.remove(item_index)
            for item in expression_list:
                if item.frame > frame:
                    item.frame -= 10

        # remove from face objects
        if len(expression_list) > 0:
            if self.remove_item:
                item = expression_list[self.remove_item]
            else:
                item = expression_list[expression_list_index]
            _remove_faceit_item(item)

        expression_count = len(expression_list)

        if expression_list_index >= expression_count:
            scene.faceit_expression_list_index = expression_count - 1

        scene.tool_settings.use_keyframe_insert_auto = auto_key
        if ow_action:
            scene.frame_start, scene.frame_end = (int(x) for x in futils.get_action_frame_range(ow_action))

        return {'FINISHED'}


# END ######################### VERSION 2 ONLY #######################


class FACEIT_OT_ExpressionInfo(bpy.types.Operator):
    '''Affiche des informations détaillées sur les expressions FaceIt chargées'''
    bl_idname = "faceit.expression_info"
    bl_label = "Information sur les Expressions"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.faceit_expression_list)

    @staticmethod
    def count_faceit_shape_keys(scene):
        """Compte le nombre de shape keys créées par FaceIt"""
        from ..core import shape_key_utils as sk_utils
        from ..core import faceit_utils as futils
        
        # Obtenir les objets FaceIt enregistrés
        faceit_objects = futils.get_faceit_objects_list()
        
        if not faceit_objects:
            return 0, []
        
        # Obtenir toutes les shape keys des objets FaceIt (exclut automatiquement "Basis")
        shape_key_names = sk_utils.get_shape_key_names_from_objects(faceit_objects)
        shape_key_count = len(shape_key_names)
        
        # Obtenir les noms des objets qui ont des shape keys
        object_names = []
        for obj in faceit_objects:
            if sk_utils.has_shape_keys(obj) and len(obj.data.shape_keys.key_blocks) > 1:  # > 1 pour exclure juste "Basis"
                object_names.append(obj.name)
        
        return shape_key_count, object_names

    def execute(self, context):
        scene = context.scene
        expressions = scene.faceit_expression_list
        
        if not expressions:
            self.report({'INFO'}, "Aucune expression FaceIt chargée")
            return {'CANCELLED'}
        
        # Compter les shape keys
        shape_key_count, faceit_objects = self.count_faceit_shape_keys(scene)
        
        # Compter les types d'expressions
        arkit_count = 0
        custom_count = 0
        
        expression_names = []
        for exp in expressions:
            expression_names.append(exp.name)
            # Simple heuristique pour détecter les expressions ARKit
            if any(arkit_name in exp.name.lower() for arkit_name in 
                   ['jaw', 'mouth', 'eye', 'brow', 'cheek', 'nose']):
                arkit_count += 1
            else:
                custom_count += 1
        
        total_count = len(expressions)
        
        # Message détaillé
        message = f"Expressions FaceIt chargées :\n"
        message += f"Total : {total_count}\n"
        message += f"Type ARKit : {arkit_count}\n"
        message += f"Personnalisées : {custom_count}\n\n"
        message += f"Shape Keys créées : {shape_key_count}\n"
        if faceit_objects:
            message += f"Objets avec shape keys : {', '.join(faceit_objects)}\n\n"
        else:
            message += "Aucun objet avec shape keys FaceIt trouvé\n\n"
        message += "Liste des expressions :\n"
        for i, name in enumerate(expression_names[:10]):  # Limite à 10 pour éviter un message trop long
            message += f"  {i+1}. {name}\n"
        
        if total_count > 10:
            message += f"  ... et {total_count - 10} autres expressions"
        
        # Afficher dans la console aussi
        print("\n" + "="*50)
        print("FACEIT EXPRESSIONS INFO")
        print("="*50)
        print(message)
        print("="*50)
        
        self.report({'INFO'}, f"Expressions: {total_count} | Shape Keys: {shape_key_count} (voir console)")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        expressions = scene.faceit_expression_list
        
        if not expressions:
            layout.label(text="Aucune expression chargée", icon='INFO')
            return
        
        # Compter les types
        arkit_count = sum(1 for exp in expressions if any(arkit_name in exp.name.lower() 
                         for arkit_name in ['jaw', 'mouth', 'eye', 'brow', 'cheek', 'nose']))
        custom_count = len(expressions) - arkit_count
        
        col = layout.column(align=True)
        col.label(text="Résumé des expressions :", icon='INFO')
        col.separator()
        
        box = col.box()
        box.label(text=f"Total : {len(expressions)} expressions")
        box.label(text=f"Type ARKit : {arkit_count}")
        box.label(text=f"Personnalisées : {custom_count}")
        
        col.separator()
        col.label(text="Liste des expressions :")
        
        box = col.box()
        for i, exp in enumerate(expressions[:8]):  # Affiche les 8 premières
            box.label(text=f"{i+1}. {exp.name}")
        
        if len(expressions) > 8:
            box.label(text=f"... et {len(expressions) - 8} autres")
