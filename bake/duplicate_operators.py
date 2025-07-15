# -*- coding: utf-8 -*-
import bpy
from bpy.props import IntProperty, FloatProperty
from bpy.types import Operator

class FACEIT_OT_DuplicateShapeKeys(Operator):
    '''Duplique l'objet actif en créant une copie pour chaque shape key avec l'expression appliquée de manière permanente'''
    bl_idname = 'faceit.duplicate_shape_keys'
    bl_label = 'Dupliquer Shape Keys'
    bl_options = {'REGISTER', 'UNDO'}

    objects_per_row: IntProperty(
        name="Objets par ligne",
        description="Nombre d'objets à placer par ligne dans la grille",
        default=10,
        min=1,
        max=20
    )
    
    spacing_multiplier_x: FloatProperty(
        name="Espacement X",
        description="Multiplicateur pour l'espacement horizontal (basé sur la largeur de l'objet)",
        default=1.5,
        min=1.0,
        max=5.0
    )
    
    spacing_multiplier_z: FloatProperty(
        name="Espacement Z",
        description="Multiplicateur pour l'espacement vertical (basé sur la profondeur de l'objet)",
        default=1.5,
        min=1.0,
        max=5.0
    )
    
    source_offset_multiplier: FloatProperty(
        name="Distance de l'objet source",
        description="Multiplicateur pour la distance par rapport à l'objet source",
        default=2.0,
        min=1.0,
        max=10.0
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        return obj.data and obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 1

    def execute(self, context):
        active_obj = context.active_object
        
        if not active_obj:
            self.report({'ERROR'}, "Veuillez sélectionner votre personnage avec les clés de forme.")
            return {'CANCELLED'}
        
        # Vérifie si l'objet a bien des clés de forme
        if not active_obj.data or not active_obj.data.shape_keys:
            self.report({'ERROR'}, f"L'objet '{active_obj.name}' n'a pas de clés de forme.")
            return {'CANCELLED'}
        
        # Paramètres de la grille
        objects_per_row = self.objects_per_row
        spacing_x = active_obj.dimensions.x * self.spacing_multiplier_x
        spacing_z = active_obj.dimensions.z * self.spacing_multiplier_z

        # Position de l'objet source
        original_world_location = active_obj.matrix_world.to_translation()
        
        # Décalage initial pour séparer les copies de l'objet source
        # On place les copies à une distance configurable de l'objet original
        base_offset = max(spacing_x, spacing_z) * self.source_offset_multiplier
        start_x = original_world_location.x + base_offset
        start_z = original_world_location.z + base_offset
        
        shape_keys = active_obj.data.shape_keys.key_blocks
        
        # Compte le nombre de shape keys à dupliquer (sans "Basis")
        shape_keys_to_duplicate = len(shape_keys) - 1
        
        if shape_keys_to_duplicate == 0:
            self.report({'WARNING'}, "Aucune shape key à dupliquer (seulement 'Basis' trouvée).")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Début de la duplication de {shape_keys_to_duplicate} shape keys...")

        # Boucle à travers chaque clé de forme (en ignorant la première, "Basis")
        for i, key in enumerate(shape_keys[1:]):
            # Assure que l'objet source est sélectionné
            bpy.ops.object.select_all(action='DESELECT')
            active_obj.select_set(True)
            context.view_layer.objects.active = active_obj

            # Remet à zéro toutes les clés de forme sur l'objet source
            for k in shape_keys:
                k.value = 0.0
            
            # Applique la clé de forme en cours
            key.value = 1.0
            
            # Duplique l'objet
            bpy.ops.object.duplicate(linked=False)
            new_obj = context.active_object

            # Convertit la copie en mesh indépendant (applique la shape key)
            bpy.ops.object.convert(target='MESH')
            
            # Renomme le nouvel objet
            new_obj.name = f"{active_obj.name}_{key.name}"
            
            # Calcule la position dans la grille (décalée par rapport à l'objet source)
            col = i % objects_per_row
            row = i // objects_per_row
            new_obj.location.x = start_x + (col * spacing_x)
            new_obj.location.y = original_world_location.y
            new_obj.location.z = start_z - (row * spacing_z)

            print(f"Objet '{new_obj.name}' créé avec l'expression '{key.name}' appliquée.")

        # Nettoyage de l'objet original (remet toutes les shape keys à 0)
        bpy.ops.object.select_all(action='DESELECT')
        active_obj.select_set(True)
        context.view_layer.objects.active = active_obj
        for k in shape_keys:
            k.value = 0.0

        self.report({'INFO'}, f"Opération terminée ! {shape_keys_to_duplicate} copies créées avec leurs expressions permanentes.")
        print(f"\nOpération terminée ! {shape_keys_to_duplicate} copies ont leur expression permanente.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        col = layout.column()
        col.prop(self, "objects_per_row")
        col.prop(self, "spacing_multiplier_x")
        col.prop(self, "spacing_multiplier_z")
        col.prop(self, "source_offset_multiplier")
        
        # Informations sur l'objet actif
        active_obj = context.active_object
        if active_obj and active_obj.data and active_obj.data.shape_keys:
            shape_keys_count = len(active_obj.data.shape_keys.key_blocks) - 1  # -1 pour "Basis"
            col.separator()
            col.label(text=f"Objet: {active_obj.name}")
            col.label(text=f"Shape Keys à dupliquer: {shape_keys_count}")
