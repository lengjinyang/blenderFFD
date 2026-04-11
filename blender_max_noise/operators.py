import bpy

from .noise_nodes import ensure_noise_modifier, remove_noise_modifier, sync_modifier_from_object


class OBJECT_OT_add_max_noise_modifier(bpy.types.Operator):
    bl_idname = "object.add_max_noise_modifier"
    bl_label = "Add Max Noise"
    bl_description = "Add a Geometry Nodes based Max Noise deformer"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        obj = context.object
        ensure_noise_modifier(obj)
        sync_modifier_from_object(obj)
        return {"FINISHED"}


class OBJECT_OT_remove_max_noise_modifier(bpy.types.Operator):
    bl_idname = "object.remove_max_noise_modifier"
    bl_label = "Remove Max Noise"
    bl_description = "Remove the Max Noise deformer and its node group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        removed = remove_noise_modifier(context.object)
        return {"FINISHED"} if removed else {"CANCELLED"}


CLASSES = (
    OBJECT_OT_add_max_noise_modifier,
    OBJECT_OT_remove_max_noise_modifier,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
