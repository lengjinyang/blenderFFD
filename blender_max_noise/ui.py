import bpy

from .noise_nodes import get_noise_modifier


def _draw_noise_settings(layout, obj):
    settings = obj.max_noise_settings
    modifier = get_noise_modifier(obj)

    row = layout.row(align=True)
    if modifier is None:
        row.operator("object.add_max_noise_modifier", text="Add Max Noise", icon="MOD_DISPLACE")
        layout.label(text="No Max Noise modifier on this object.", icon="INFO")
        return

    row.operator("object.add_max_noise_modifier", text="Refresh", icon="FILE_REFRESH")
    row.operator("object.remove_max_noise_modifier", text="Remove", icon="X")

    layout.label(text=f"Using modifier: {modifier.name}", icon="GEOMETRY_NODES")

    col = layout.column(align=True)
    col.prop(settings, "noise_type")
    col.prop(settings, "space")

    box = layout.box()
    box.label(text="Strength")
    box.prop(settings, "strength", text="")
    axis_row = box.row(align=True)
    axis_row.label(text="Axis Lock")
    axis_row.prop(settings, "use_axis_x", toggle=True)
    axis_row.prop(settings, "use_axis_y", toggle=True)
    axis_row.prop(settings, "use_axis_z", toggle=True)

    box = layout.box()
    box.label(text="Noise Scale")
    box.prop(settings, "size")
    box.prop(settings, "use_non_uniform_scale")
    if settings.use_non_uniform_scale:
        box.prop(settings, "scale_xyz", text="")

    box = layout.box()
    box.label(text="Noise Pattern")
    box.prop(settings, "seed")
    box.prop(settings, "phase")
    if settings.noise_type != "BASIC":
        box.prop(settings, "iterations")
        box.prop(settings, "roughness")

    box = layout.box()
    box.label(text="Safety")
    box.prop(settings, "clamp_limit")

    box = layout.box()
    box.label(text="Animation")
    box.prop(settings, "animate_over_time")
    row = box.row()
    row.enabled = settings.animate_over_time
    row.prop(settings, "animation_speed")


class _MaxNoisePanelBase:
    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"


class OBJECT_PT_max_noise_modifier(_MaxNoisePanelBase, bpy.types.Panel):
    bl_label = "Max Noise"
    bl_idname = "OBJECT_PT_max_noise_modifier"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "modifier"

    def draw(self, context):
        _draw_noise_settings(self.layout, context.object)


class VIEW3D_PT_max_noise_modifier(_MaxNoisePanelBase, bpy.types.Panel):
    bl_label = "Max Noise"
    bl_idname = "VIEW3D_PT_max_noise_modifier"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Max Noise"

    def draw(self, context):
        _draw_noise_settings(self.layout, context.object)


CLASSES = (
    OBJECT_PT_max_noise_modifier,
    VIEW3D_PT_max_noise_modifier,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
