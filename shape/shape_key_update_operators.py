import bpy

def get_keys_for_dropdown(self, context):
    props = context.scene.shape_key_updater_props
    source_obj = props.source_object
    if not source_obj:
        return [('__NONE__', "Choisissez un Objet Source", "")]
    if not hasattr(source_obj.data, 'shape_keys') or not source_obj.data.shape_keys:
        return [('__NONE__', "Cet objet n'a pas de clés", "")]
    items = [(k.name, k.name, "") for k in source_obj.data.shape_keys.key_blocks if k.name != "Basis"]
    if not items:
        return [('__NONE__', "Aucune clé modifiable", "")]
    return items

class SK_UpdaterProperties(bpy.types.PropertyGroup):
    source_object: bpy.props.PointerProperty(
        name="Objet Source",
        description="L'objet qui a les clés de forme à modifier",
        type=bpy.types.Object,
    )
    target_object: bpy.props.PointerProperty(
        name="Maillage Cible",
        description="Le maillage qui a la nouvelle forme",
        type=bpy.types.Object,
    )
    shape_key_to_update: bpy.props.EnumProperty(
        name="Clé à Écraser",
        description="Choisissez la clé de forme à mettre à jour",
        items=get_keys_for_dropdown,
    )

class OBJECT_OT_proper_update_shapekey(bpy.types.Operator):
    bl_idname = "object.proper_update_shapekey"
    bl_label = "Mettre à jour Clé de Forme (Faceit)"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        props = context.scene.shape_key_updater_props
        active = context.active_object
        selected = context.selected_objects
        if active:
            props.source_object = active
        if len(selected) == 2:
            target = [obj for obj in selected if obj != active]
            if target:
                props.target_object = target[0]
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        props = context.scene.shape_key_updater_props
        layout = self.layout
        layout.prop(props, "source_object")
        layout.prop(props, "target_object")
        layout.separator()
        layout.prop(props, "shape_key_to_update")

    def execute(self, context):
        props = context.scene.shape_key_updater_props
        source_obj = props.source_object
        target_obj = props.target_object
        key_name = props.shape_key_to_update
        if not source_obj or not target_obj:
            self.report({'ERROR'}, "Les objets Source et Cible doivent être définis.")
            return {'CANCELLED'}
        if key_name == '__NONE__' or not key_name:
            self.report({'ERROR'}, "Veuillez sélectionner une clé de forme valide.")
            return {'CANCELLED'}
        shape_key = source_obj.data.shape_keys.key_blocks.get(key_name)
        if not shape_key:
            self.report({'ERROR'}, "Clé de forme introuvable.")
            return {'CANCELLED'}
        if len(source_obj.data.vertices) != len(target_obj.data.vertices):
            self.report({'ERROR'}, "Le nombre de sommets doit être identique.")
            return {'CANCELLED'}
        for i, vert in enumerate(shape_key.data):
            vert.co = target_obj.data.vertices[i].co
        self.report({'INFO'}, f"SUCCÈS : La clé '{key_name}' a été mise à jour.")
        return {'FINISHED'}

# --- Enregistrement pour Faceit ---
classes = (
    SK_UpdaterProperties,
    OBJECT_OT_proper_update_shapekey
)

def register_shape_key_update():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.shape_key_updater_props = bpy.props.PointerProperty(type=SK_UpdaterProperties)

def unregister_shape_key_update():
    del bpy.types.Scene.shape_key_updater_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
