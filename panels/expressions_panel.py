
import bpy

from ..core.shape_key_utils import has_shape_keys

from ..core.faceit_utils import get_faceit_armature
from . import draw_utils
from .ui import FACEIT_PT_Base


class FACEIT_PT_BaseExpressions(FACEIT_PT_Base):
    UI_TABS = ('EXPRESSIONS',)

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        return bool(get_faceit_armature())


class FACEIT_PT_Expressions(FACEIT_PT_BaseExpressions, bpy.types.Panel):
    '''The expressions Panel'''
    bl_label = 'Expressions'
    bl_options = set()
    bl_idname = 'FACEIT_PT_Expressions'
    weblink = "https://faceit-doc.readthedocs.io/en/latest/expressions/"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        rig = get_faceit_armature()
        return rig.name in context.scene.objects

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rig = get_faceit_armature()
        shapes_baked = rig.hide_viewport is True or scene.faceit_shapes_generated
        col = layout.column(align=True)

        # Compteur d'expressions et shape keys - toujours visible s'il y en a
        if scene.faceit_expression_list:
            expression_count = len(scene.faceit_expression_list)
            
            # Compter les shape keys (utilise la même logique que l'opérateur ExpressionInfo)
            from ..animate.animate_operators import FACEIT_OT_ExpressionInfo
            shape_key_count, _ = FACEIT_OT_ExpressionInfo.count_faceit_shape_keys(scene)
            
            box = col.box()
            row = box.row()
            row.label(text=f"📊 Expressions : {expression_count} | Shape Keys : {shape_key_count}", icon='INFO')
            if expression_count > 0:
                row.operator('faceit.expression_info', text='', icon='QUESTION')
            col.separator()

        # row = col.row()
        # row.label(text='Expressions')
        # if scene.faceit_version == 2:
        #     draw_utils.draw_web_link(row, 'https://faceit-doc.readthedocs.io/en/latest/expressions-2-0/')
        # else:
        #     draw_utils.draw_web_link(row, 'https://faceit-doc.readthedocs.io/en/latest/expressions/')

        # col.separator()

# START ####################### VERSION 2 ONLY #######################

        if not shapes_baked and scene.faceit_version == 2:
            box = col.box()
            row = box.row()
            if scene.faceit_expression_init_expand_ui:
                icon = 'TRIA_DOWN'
            else:
                icon = 'TRIA_RIGHT'

            row.prop(scene, 'faceit_expression_init_expand_ui', text='Create',
                     icon=icon, icon_only=True, emboss=False)
            draw_utils.draw_web_link(row, link="https://faceit-doc.readthedocs.io/en/latest/create-expressions/")
            if scene.faceit_expression_init_expand_ui:
                col_above_list = box.column(align=True)
                
                # Indicateur d'état des expressions
                expression_count = len(scene.faceit_expression_list)
                if expression_count > 0:
                    info_box = col_above_list.box()
                    info_box.label(text=f"✅ {expression_count} expressions déjà chargées", icon='CHECKMARK')
                else:
                    info_box = col_above_list.box()
                    info_box.label(text="❌ Aucune expression chargée", icon='ERROR')
                col_above_list.separator()
                
                if shapes_baked:
                    col_above_list.enabled = False
                if scene.faceit_armature_type == 'ANY':
                    # if not rig.data.faceit_control_bones:
                    #     draw_utils.draw_text_block(
                    #         col_above_list,
                    #         text="No Control Bones registered for Faceit Rig (see Setup).",
                    #         heading_icon='ERROR'
                    #     )
                    row = col_above_list.row(align=True)
                    row.operator("faceit.register_control_bones",
                                 text="Register Control Bones (Pose Mode)", icon='ADD')
                    row.operator("faceit.select_control_bones", text="", icon='RESTRICT_SELECT_OFF')
                    row.operator("faceit.clear_control_bones", text="", icon='X')
                    row = col_above_list.row(align=True)
                    row.operator("faceit.update_control_bones")
                    col_above_list.separator()
                    row = col_above_list.row(align=True)
                    # row.operator('faceit.load_empty_expressions', text='Load Empty Expressions', icon='ACTION')
                    row.operator('faceit.append_action_to_faceit_rig', text='Load Empty Expressions', icon='ACTION')
                else:
                    row = col_above_list.row(align=True)
                    row.operator('faceit.append_action_to_faceit_rig', text='Load Faceit Expressions', icon='ACTION')
                row = col_above_list.row(align=True)
                op = row.operator('faceit.append_action_to_faceit_rig',
                                  text='Load Custom Expressions', icon='IMPORT')
                op.load_custom_path = True
                row.operator('faceit.export_expressions', text='Export Custom Expressions', icon='EXPORT')
                row = col_above_list.row(align=True)
                op = row.operator('faceit.add_expression_item', text='Add Custom Expression', icon='ADD')
                op.custom_shape = True

# END ######################### VERSION 2 ONLY #######################

# START ######################### VERSION 1 ONLY #######################
        if not shapes_baked and scene.faceit_version == 1:
            row = col.row(align=True)
            # TODO: check for the rig type. Version 1 should probably only work with Rigify rigs...
            op = row.operator('faceit.append_action_to_faceit_rig',
                              text='Load ARKit Expressions', icon='ACTION')
            op.is_version_one = True
            op.load_method = 'OVERWRITE'
            op.expressions_type = 'ARKIT'

# END ######################### VERSION 1 ONLY #######################

        if shapes_baked:
            row = col.row()
            row.label(text="Return")
            row = col.row()
            row.operator('faceit.back_to_rigging', icon='BACK')
            col.separator(factor=2)
            
            # Compteur d'expressions (mode baked)
            expression_count = len(scene.faceit_expression_list)
            row = col.row()
            row.label(text=f"Expressions générées : {expression_count}", icon='INFO')
            row = col.row()
            row.operator('faceit.expression_info', text='Détails', icon='QUESTION')
            
            row = col.row()
            row.template_list('FACEIT_UL_ExpressionsBaked', '', bpy.context.scene,
                              'faceit_expression_list', scene, 'faceit_expression_list_index')
            row = col.row(align=True)
            row.label(text='Testing')
            row = col.row(align=True)
            row.operator('faceit.test_action', icon='ACTION')
        elif 'overwrite_shape_action' in bpy.data.actions and scene.faceit_expression_list:
            col.separator()
            
            # Compteur d'expressions
            expression_count = len(scene.faceit_expression_list)
            row = col.row()
            row.label(text=f"Expressions chargées : {expression_count}", icon='INFO')
            row = col.row()
            row.operator('faceit.expression_info', text='Détails', icon='QUESTION')
            
            row = col.row()
            row.template_list('FACEIT_UL_Expressions', '', bpy.context.scene,
                              'faceit_expression_list', scene, 'faceit_expression_list_index')
            col_ul = row.column(align=True)

# START ####################### VERSION 2 ONLY #######################

            if scene.faceit_version == 2:

                row = col_ul.row(align=True)
                op = row.operator('faceit.add_expression_item', text='', icon='ADD')
                op.custom_shape = True

                row = col_ul.row(align=True)
                op = row.operator('faceit.remove_expression_item', text='', icon='REMOVE')
                # op.prompt = False

# END ######################### VERSION 2 ONLY #######################

            col_ul.separator()
            col_ul.row().menu('FACEIT_MT_ExpressionList', text='', icon='DOWNARROW_HLT')
            col_ul.separator()
            # Move the indices
            row = col_ul.row(align=True)
            op = row.operator('faceit.move_expression_item', text='', icon='TRIA_UP')
            op.direction = 'UP'
            row = col_ul.row(align=True)
            op = row.operator('faceit.move_expression_item', text='', icon='TRIA_DOWN')
            op.direction = 'DOWN'
            row = col.row()
            row.operator('faceit.force_zero_frames', icon='FILE_REFRESH')

        elif 'overwrite_shape_action' not in bpy.data.actions and scene.faceit_expression_list:
            col.separator()
            row = col.row()
            draw_utils.draw_text_block(context, row, text='The Expression Action has been deleted.')


class FACEIT_PT_ExpressionOptions(FACEIT_PT_BaseExpressions, bpy.types.Panel):
    bl_label = 'Options'
    bl_idname = 'FACEIT_PT_ExpressionOptions'
    bl_options = set()
    faceit_predecessor = 'FACEIT_PT_Expressions'
    weblink = ""

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        scene = context.scene
        rig = scene.faceit_armature
        if rig:
            if rig.hide_viewport is True or scene.faceit_shapes_generated:
                return False
        else:
            return False
        return 'overwrite_shape_action' in bpy.data.actions and scene.faceit_expression_list

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(scene, 'faceit_use_auto_mirror_x',
                 text='Auto Mirror X', icon='MOD_MIRROR')
        row = col.row(align=True)
        row.prop(scene.tool_settings, 'use_keyframe_insert_auto', icon='RADIOBUT_ON')
        col.separator()
        row = col.row(align=True)
        row.label(text='Corrective Sculpting')
        row = col.row(align=True)
        row.prop(scene, 'faceit_use_corrective_shapes', icon='SCULPTMODE_HLT')
        if scene.faceit_use_corrective_shapes:
            row = col.row(align=True)
            row.prop(scene, 'faceit_try_mirror_corrective_shapes', expand=True, icon='MOD_MIRROR')
            # row = col.row(align=True)
            row.prop(scene, 'faceit_corrective_sk_mirror_affect_only_selected_objects',
                     text='', icon='RESTRICT_SELECT_OFF')
            if scene.faceit_try_mirror_corrective_shapes:
                row = col.row(align=True)
                row.prop(scene, 'faceit_corrective_sk_mirror_method', expand=True, icon='MOD_MIRROR')
            row = col.row(align=True)
            row.label(text='Edit Mode')
            row = col.row(align=True)
            row.prop(scene, 'faceit_corrective_shape_keys_edit_mode', icon='EDITMODE_HLT', expand=True)


class FACEIT_UL_Expressions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            scene = context.scene
            row = layout.row(align=True)
            row.prop(item, 'name', text='', emboss=False, icon='KEYFRAME')
            if item.mirror_name:
                op = row.operator('faceit.mirror_copy_expression', text='', icon='MOD_MIRROR')
                op.expression_to_mirror = item.name
            elif scene.faceit_use_auto_mirror_x:
                row.label(text='', icon='MOD_MIRROR')
            # Note: faceit.pose_amplify et faceit.reset_expression n'existent pas dans le code actuel
            # Utilisation d'opérateurs alternatifs ou désactivation temporaire
            # op = row.operator('faceit.set_amplify_values', text='', icon='ARROW_LEFTRIGHT')
            # op = row.operator('faceit.reset_expression_values', text='', icon='LOOP_BACK')
            row.label(text='', icon='ARROW_LEFTRIGHT')  # Placeholder pour l'amplification 
            op = row.operator('faceit.reset_expression_values', text='', icon='LOOP_BACK')
            # op.expression_to_reset = item.name  # Cette propriété n'existe peut-être pas
            if scene.faceit_use_corrective_shapes:
                op = row.operator('faceit.add_corrective_shape_key_to_expression', text='', icon='SCULPTMODE_HLT')
                op.expression = item.name
                sub = row.row(align=True)
                if item.corr_shape_key:
                    op = sub.operator('faceit.remove_corrective_shape_key', text='', icon='X')
                    op.expression = item.name
                else:
                    op = sub.operator('faceit.remove_corrective_shape_key', text='',
                                      emboss=False, icon='RADIOBUT_OFF')
                    op.expression = item.name
                    sub.enabled = False


class FACEIT_UL_ExpressionsBaked(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'name', text='', emboss=False, icon='KEYFRAME')


class FACEIT_MT_ExpressionList(bpy.types.Menu):
    bl_label = 'Expression List Menu'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        row.operator('faceit.load_arkit_refernce', icon='USER')
        if scene.faceit_version == 2:
            row = layout.row()
            row.operator('faceit.clear_faceit_expressions', icon='TRASH')
        row = layout.row(align=True)
        op = row.operator('faceit.force_zero_frames', icon='FILE_REFRESH')
        row = layout.row(align=True)
        op = row.operator('faceit.cleanup_unused_fcurves', icon='FCURVE')
        row = layout.row(align=True)
        op = row.operator('faceit.reevaluate_corrective_shape_keys', icon='SHAPEKEY_DATA')
