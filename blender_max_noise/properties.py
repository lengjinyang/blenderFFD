import bpy

from .constants import MAX_OCTAVES


def _update_settings(self, context):
    if context is None:
        return
    obj = getattr(context, "object", None)
    if obj is None or obj.type != "MESH":
        return

    from .noise_nodes import sync_modifier_from_object

    sync_modifier_from_object(obj)


class MaxNoiseSettings(bpy.types.PropertyGroup):
    modifier_name: bpy.props.StringProperty(
        name="Modifier Name",
        default="",
        options={"HIDDEN"},
    )

    noise_type: bpy.props.EnumProperty(
        name="Noise Type",
        items=(
            ("BASIC", "Basic Noise", "Single octave procedural noise"),
            ("FRACTAL", "Fractal Noise", "Multi octave fractal noise"),
            ("TURBULENCE", "Turbulence", "Ridged turbulence style deformation"),
        ),
        default="BASIC",
        update=_update_settings,
    )

    strength: bpy.props.FloatVectorProperty(
        name="Strength",
        subtype="XYZ",
        size=3,
        default=(0.25, 0.25, 0.25),
        update=_update_settings,
    )

    size: bpy.props.FloatProperty(
        name="Noise Size",
        description="Uniform size of the noise pattern",
        default=1.0,
        min=0.0001,
        soft_min=0.01,
        update=_update_settings,
    )

    use_non_uniform_scale: bpy.props.BoolProperty(
        name="Use Non-Uniform Scale",
        description="Enable per-axis scaling of the sampled noise field",
        default=False,
        update=_update_settings,
    )

    scale_xyz: bpy.props.FloatVectorProperty(
        name="Scale XYZ",
        subtype="XYZ",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.0001,
        soft_min=0.01,
        update=_update_settings,
    )

    seed: bpy.props.IntProperty(
        name="Seed",
        default=0,
        update=_update_settings,
    )

    phase: bpy.props.FloatProperty(
        name="Phase",
        description="Offset into the procedural field, useful for animation",
        default=0.0,
        update=_update_settings,
    )

    animate_over_time: bpy.props.BoolProperty(
        name="Animate Over Time",
        default=False,
        update=_update_settings,
    )

    animation_speed: bpy.props.FloatProperty(
        name="Animation Speed",
        default=1.0,
        soft_min=0.0,
        update=_update_settings,
    )

    iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Fractal octave count",
        default=4,
        min=1,
        max=MAX_OCTAVES,
        update=_update_settings,
    )

    roughness: bpy.props.FloatProperty(
        name="Roughness",
        description="Fractal roughness for additional octaves",
        default=0.5,
        min=0.0,
        max=1.0,
        update=_update_settings,
    )

    clamp_limit: bpy.props.FloatProperty(
        name="Clamp Limit",
        description="Maximum displacement allowed per axis to avoid extreme deformation",
        default=2.5,
        min=0.0001,
        soft_min=0.05,
        update=_update_settings,
    )

    use_axis_x: bpy.props.BoolProperty(
        name="X",
        description="Allow displacement along X",
        default=True,
        update=_update_settings,
    )

    use_axis_y: bpy.props.BoolProperty(
        name="Y",
        description="Allow displacement along Y",
        default=True,
        update=_update_settings,
    )

    use_axis_z: bpy.props.BoolProperty(
        name="Z",
        description="Allow displacement along Z",
        default=True,
        update=_update_settings,
    )

    space: bpy.props.EnumProperty(
        name="Space",
        items=(
            ("OBJECT", "Object Space", "Sample noise in the object's local coordinates"),
            ("WORLD", "World Space", "Sample noise in world space so the field stays fixed in the scene"),
        ),
        default="OBJECT",
        update=_update_settings,
    )


CLASSES = (
    MaxNoiseSettings,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.max_noise_settings = bpy.props.PointerProperty(type=MaxNoiseSettings)


def unregister():
    del bpy.types.Object.max_noise_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
