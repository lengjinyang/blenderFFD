import random
import uuid

import bpy

from .constants import MAX_OCTAVES, MODIFIER_NAME, MODIFIER_TAG, NODE_GROUP_PREFIX


AXIS_LABELS = ("X", "Y", "Z")
PRIMARY_BLEND = 0.72
SECONDARY_BLEND = 0.28
SHAPE_GAMMA = 1.35
WEIGHT_FLOOR = 1.0e-5


def _find_socket(sockets, name=None, index=None):
    if name is not None:
        for socket in sockets:
            if socket.name == name:
                return socket
    if index is not None:
        return sockets[index]
    raise KeyError(f"Socket not found: {name!r}")


def _set_node_position(node, x, y):
    node.location = (x, y)
    return node


def _remove_all_links(tree, to_socket):
    for link in list(tree.links):
        if link.to_socket == to_socket:
            tree.links.remove(link)


def _relink(tree, from_socket, to_socket):
    _remove_all_links(tree, to_socket)
    tree.links.new(from_socket, to_socket)


def _new_node(nodes, node_type, name, x, y):
    node = nodes.new(node_type)
    node.name = name
    node.label = name
    _set_node_position(node, x, y)
    return node


def _new_math(nodes, name, operation, x, y):
    node = _new_node(nodes, "ShaderNodeMath", name, x, y)
    node.operation = operation
    return node


def _new_vector_math(nodes, name, operation, x, y):
    node = _new_node(nodes, "ShaderNodeVectorMath", name, x, y)
    node.operation = operation
    return node


def _new_value(nodes, name, x, y, value=0.0):
    node = _new_node(nodes, "ShaderNodeValue", name, x, y)
    node.outputs[0].default_value = value
    return node


def _new_combine_xyz(nodes, name, x, y, values=(0.0, 0.0, 0.0)):
    node = _new_node(nodes, "ShaderNodeCombineXYZ", name, x, y)
    _set_combine_xyz(node, values)
    return node


def _new_noise(nodes, name, x, y):
    node = _new_node(nodes, "ShaderNodeTexNoise", name, x, y)
    node.noise_dimensions = "4D"
    _find_socket(node.inputs, "Scale", 1).default_value = 1.0
    _find_socket(node.inputs, "Detail", 2).default_value = 0.0
    _find_socket(node.inputs, "Roughness", 3).default_value = 0.0
    if len(node.inputs) > 4:
        _find_socket(node.inputs, "Lacunarity", 4).default_value = 2.0
    if len(node.inputs) > 5:
        _find_socket(node.inputs, "Distortion", 5).default_value = 0.0
    return node


def _add_group_socket(group, name, in_out, socket_type):
    if hasattr(group, "interface"):
        return group.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    if in_out == "INPUT":
        return group.inputs.new(socket_type, name)
    return group.outputs.new(socket_type, name)


def _set_group_capabilities(group):
    for attr in ("is_modifier", "is_type_mesh", "is_mode_object"):
        if hasattr(group, attr):
            setattr(group, attr, True)


def _global_seed_offset(seed):
    return _seed_vector(seed, 0)


def _axis_seed_offset(seed, axis_index):
    return _seed_vector(seed, 101 + axis_index * 17)


def _secondary_offset(axis_index, octave_index):
    base = (
        (3.75, 11.2, -5.4),
        (-9.1, 4.85, 7.3),
        (6.4, -8.75, 12.6),
    )[axis_index]
    factor = octave_index + 1
    return tuple(component * factor for component in base)


def _seed_vector(seed, salt):
    rng = random.Random((int(seed) * 92821) + (salt * 68917) + 17)
    return (
        rng.uniform(-10000.0, 10000.0),
        rng.uniform(-10000.0, 10000.0),
        rng.uniform(-10000.0, 10000.0),
    )


def _base_name(key):
    return {
        "group_input": "Group Input",
        "group_output": "Group Output",
        "set_position": "Set Position",
        "position": "Local Position",
        "self_object": "Self Object",
        "object_info": "Self Object Info",
        "world_scale": "World Scale",
        "world_rotate": "World Rotate",
        "world_translate": "World Translate",
        "sample_scale": "Sample Scale",
        "sample_scale_vector": "Sample Scale Vector",
        "global_seed": "Global Seed Offset",
        "global_seed_add": "Global Seed Add",
        "phase_value": "Phase Value",
        "animate_value": "Animate Toggle",
        "speed_value": "Animation Speed",
        "iterations_value": "Iterations Value",
        "roughness_value": "Roughness Value",
        "clamp_value": "Clamp Value",
        "scene_time": "Scene Time",
        "time_multiply": "Time Multiply",
        "time_enable": "Time Enable",
        "phase_add": "Phase Add",
        "strength": "Strength Vector",
        "combined_signed": "Combined Signed Vector",
        "combined_turbulence": "Combined Turbulence Vector",
        "final_multiply": "Final Multiply",
        "final_separate": "Final Separate",
        "clamped_combine": "Clamped Combine",
    }[key]


def _axis_seed_name(axis_label):
    return f"Axis Seed {axis_label}"


def _axis_base_name(axis_label):
    return f"Axis Base {axis_label}"


def _axis_output_name(axis_label, variant):
    return f"Axis {axis_label} {variant}"


def _clamp_axis_name(axis_label, suffix):
    return f"Clamp {axis_label} {suffix}"


def _node(nodes, name):
    return nodes[name]


def _signed_noise_output(nodes, links, source_socket, prefix, x, y):
    multiply = _new_math(nodes, f"{prefix} * 2", "MULTIPLY", x, y)
    multiply.inputs[1].default_value = 2.0
    subtract = _new_math(nodes, f"{prefix} - 1", "SUBTRACT", x + 150, y)
    subtract.inputs[1].default_value = 1.0

    links.new(source_socket, multiply.inputs[0])
    links.new(multiply.outputs[0], subtract.inputs[0])
    return subtract.outputs[0]


def _shape_signed_output(nodes, links, signed_socket, prefix, x, y):
    absolute = _new_math(nodes, f"{prefix} Abs", "ABSOLUTE", x, y)
    power = _new_math(nodes, f"{prefix} Shape", "POWER", x + 150, y)
    power.inputs[1].default_value = SHAPE_GAMMA
    sign = _new_math(nodes, f"{prefix} Sign", "SIGN", x, y - 120)
    combine = _new_math(nodes, f"{prefix} Reapply Sign", "MULTIPLY", x + 300, y)

    links.new(signed_socket, absolute.inputs[0])
    links.new(absolute.outputs[0], power.inputs[0])
    links.new(signed_socket, sign.inputs[0])
    links.new(sign.outputs[0], combine.inputs[0])
    links.new(power.outputs[0], combine.inputs[1])
    return combine.outputs[0]


def _turbulence_output(nodes, links, signed_socket, prefix, x, y):
    absolute = _new_math(nodes, f"{prefix} Turbulence Abs", "ABSOLUTE", x, y)
    multiply = _new_math(nodes, f"{prefix} Turbulence * 2", "MULTIPLY", x + 150, y)
    multiply.inputs[1].default_value = 2.0
    subtract = _new_math(nodes, f"{prefix} Turbulence - 1", "SUBTRACT", x + 300, y)
    subtract.inputs[1].default_value = 1.0

    links.new(signed_socket, absolute.inputs[0])
    links.new(absolute.outputs[0], multiply.inputs[0])
    links.new(multiply.outputs[0], subtract.inputs[0])
    return subtract.outputs[0]


def _build_octave_layer(nodes, links, axis_socket, phase_socket, roughness_socket, iterations_socket, axis_label, axis_index, octave_index, x, y):
    frequency = 2.0 ** octave_index

    frequency_vector = _new_combine_xyz(
        nodes,
        f"{axis_label} Octave {octave_index} Frequency",
        x,
        y + 120,
        (frequency, frequency, frequency),
    )
    scale_vector = _new_vector_math(nodes, f"{axis_label} Octave {octave_index} Scale", "MULTIPLY", x + 180, y + 40)
    primary_noise = _new_noise(nodes, f"{axis_label} Octave {octave_index} Primary Noise", x + 400, y + 40)

    secondary_offset = _new_combine_xyz(
        nodes,
        f"{axis_label} Octave {octave_index} Secondary Offset",
        x + 180,
        y - 180,
        _secondary_offset(axis_index, octave_index),
    )
    secondary_add = _new_vector_math(nodes, f"{axis_label} Octave {octave_index} Secondary Add", "ADD", x + 400, y - 120)
    secondary_noise = _new_noise(nodes, f"{axis_label} Octave {octave_index} Secondary Noise", x + 620, y - 120)

    primary_signed = _signed_noise_output(
        nodes,
        links,
        _find_socket(primary_noise.outputs, "Fac", 0),
        f"{axis_label} Octave {octave_index} Primary Signed",
        x + 840,
        y + 40,
    )
    secondary_signed = _signed_noise_output(
        nodes,
        links,
        _find_socket(secondary_noise.outputs, "Fac", 0),
        f"{axis_label} Octave {octave_index} Secondary Signed",
        x + 840,
        y - 120,
    )

    primary_weight = _new_math(nodes, f"{axis_label} Octave {octave_index} Primary Blend", "MULTIPLY", x + 1080, y + 40)
    primary_weight.inputs[1].default_value = PRIMARY_BLEND
    secondary_weight = _new_math(nodes, f"{axis_label} Octave {octave_index} Secondary Blend", "MULTIPLY", x + 1080, y - 120)
    secondary_weight.inputs[1].default_value = SECONDARY_BLEND
    combined = _new_math(nodes, f"{axis_label} Octave {octave_index} Combined", "ADD", x + 1280, y - 20)

    links.new(axis_socket, scale_vector.inputs[0])
    links.new(frequency_vector.outputs[0], scale_vector.inputs[1])

    links.new(scale_vector.outputs[0], _find_socket(primary_noise.inputs, "Vector", 0))
    links.new(phase_socket, _find_socket(primary_noise.inputs, "W", 6 if len(primary_noise.inputs) > 6 else 4))

    links.new(scale_vector.outputs[0], secondary_add.inputs[0])
    links.new(secondary_offset.outputs[0], secondary_add.inputs[1])
    links.new(secondary_add.outputs[0], _find_socket(secondary_noise.inputs, "Vector", 0))
    links.new(phase_socket, _find_socket(secondary_noise.inputs, "W", 6 if len(secondary_noise.inputs) > 6 else 4))

    links.new(primary_signed, primary_weight.inputs[0])
    links.new(secondary_signed, secondary_weight.inputs[0])
    links.new(primary_weight.outputs[0], combined.inputs[0])
    links.new(secondary_weight.outputs[0], combined.inputs[1])

    shaped = _shape_signed_output(
        nodes,
        links,
        combined.outputs[0],
        f"{axis_label} Octave {octave_index}",
        x + 1480,
        y - 20,
    )
    turbulence = _turbulence_output(
        nodes,
        links,
        shaped,
        f"{axis_label} Octave {octave_index}",
        x + 1860,
        y - 20,
    )

    gate = _new_math(nodes, f"{axis_label} Octave {octave_index} Gate", "GREATER_THAN", x + 1480, y - 220)
    gate.inputs[1].default_value = octave_index + 0.5

    if octave_index == 0:
        weight_socket = _new_value(nodes, f"{axis_label} Octave {octave_index} Weight", x + 1680, y - 340, 1.0).outputs[0]
    else:
        weight_power = _new_math(nodes, f"{axis_label} Octave {octave_index} Weight", "POWER", x + 1680, y - 340)
        weight_power.inputs[1].default_value = float(octave_index)
        links.new(roughness_socket, weight_power.inputs[0])
        weight_socket = weight_power.outputs[0]

    gated_weight = _new_math(nodes, f"{axis_label} Octave {octave_index} Gated Weight", "MULTIPLY", x + 1880, y - 300)
    signed_weighted = _new_math(nodes, f"{axis_label} Octave {octave_index} Signed Weighted", "MULTIPLY", x + 2080, y - 40)
    turbulence_weighted = _new_math(nodes, f"{axis_label} Octave {octave_index} Turbulence Weighted", "MULTIPLY", x + 2080, y - 200)

    links.new(iterations_socket, gate.inputs[0])
    links.new(gate.outputs[0], gated_weight.inputs[0])
    links.new(weight_socket, gated_weight.inputs[1])

    links.new(shaped, signed_weighted.inputs[0])
    links.new(gated_weight.outputs[0], signed_weighted.inputs[1])
    links.new(turbulence, turbulence_weighted.inputs[0])
    links.new(gated_weight.outputs[0], turbulence_weighted.inputs[1])

    return {
        "signed": signed_weighted.outputs[0],
        "turbulence": turbulence_weighted.outputs[0],
        "weight": gated_weight.outputs[0],
    }


def _build_axis_output(nodes, links, base_socket, phase_socket, roughness_socket, iterations_socket, axis_label, axis_index, x, y):
    axis_seed = _new_combine_xyz(nodes, _axis_seed_name(axis_label), x, y + 180)
    axis_base = _new_vector_math(nodes, _axis_base_name(axis_label), "ADD", x + 220, y + 60)

    links.new(base_socket, axis_base.inputs[0])
    links.new(axis_seed.outputs[0], axis_base.inputs[1])

    layers = []
    for octave_index in range(MAX_OCTAVES):
        layer_y = y - (octave_index * 420)
        layers.append(
            _build_octave_layer(
                nodes,
                links,
                axis_base.outputs[0],
                phase_socket,
                roughness_socket,
                iterations_socket,
                axis_label,
                axis_index,
                octave_index,
                x + 500,
                layer_y,
            )
        )

    signed_sum_socket = layers[0]["signed"]
    turbulence_sum_socket = layers[0]["turbulence"]
    weight_sum_socket = layers[0]["weight"]

    chain_x = x + 2900
    for octave_index, layer in enumerate(layers[1:], 1):
        signed_add = _new_math(nodes, f"{axis_label} Signed Sum {octave_index}", "ADD", chain_x, y - (octave_index * 180))
        turbulence_add = _new_math(nodes, f"{axis_label} Turbulence Sum {octave_index}", "ADD", chain_x, y - (octave_index * 180) - 90)
        weight_add = _new_math(nodes, f"{axis_label} Weight Sum {octave_index}", "ADD", chain_x, y - (octave_index * 180) - 180)

        links.new(signed_sum_socket, signed_add.inputs[0])
        links.new(layer["signed"], signed_add.inputs[1])
        links.new(turbulence_sum_socket, turbulence_add.inputs[0])
        links.new(layer["turbulence"], turbulence_add.inputs[1])
        links.new(weight_sum_socket, weight_add.inputs[0])
        links.new(layer["weight"], weight_add.inputs[1])

        signed_sum_socket = signed_add.outputs[0]
        turbulence_sum_socket = turbulence_add.outputs[0]
        weight_sum_socket = weight_add.outputs[0]

    safe_weight = _new_math(nodes, f"{axis_label} Safe Weight", "MAXIMUM", chain_x + 220, y - 220)
    safe_weight.inputs[1].default_value = WEIGHT_FLOOR
    normalized_signed = _new_math(nodes, _axis_output_name(axis_label, "Signed"), "DIVIDE", chain_x + 440, y - 120)
    normalized_turbulence = _new_math(nodes, _axis_output_name(axis_label, "Turbulence"), "DIVIDE", chain_x + 440, y - 260)

    links.new(weight_sum_socket, safe_weight.inputs[0])
    links.new(signed_sum_socket, normalized_signed.inputs[0])
    links.new(safe_weight.outputs[0], normalized_signed.inputs[1])
    links.new(turbulence_sum_socket, normalized_turbulence.inputs[0])
    links.new(safe_weight.outputs[0], normalized_turbulence.inputs[1])

    return normalized_signed.outputs[0], normalized_turbulence.outputs[0]


def _build_clamp_axis(nodes, links, component_socket, clamp_socket, axis_label, x, y):
    negate = _new_math(nodes, _clamp_axis_name(axis_label, "Negate"), "MULTIPLY", x, y)
    negate.inputs[1].default_value = -1.0
    clamp_min = _new_math(nodes, _clamp_axis_name(axis_label, "Min"), "MAXIMUM", x + 180, y)
    clamp_max = _new_math(nodes, _clamp_axis_name(axis_label, "Max"), "MINIMUM", x + 360, y)

    links.new(clamp_socket, negate.inputs[0])
    links.new(component_socket, clamp_min.inputs[0])
    links.new(negate.outputs[0], clamp_min.inputs[1])
    links.new(clamp_min.outputs[0], clamp_max.inputs[0])
    links.new(clamp_socket, clamp_max.inputs[1])
    return clamp_max.outputs[0]


def build_node_group(name):
    group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")
    _set_group_capabilities(group)

    _add_group_socket(group, "Geometry", "INPUT", "NodeSocketGeometry")
    _add_group_socket(group, "Geometry", "OUTPUT", "NodeSocketGeometry")

    nodes = group.nodes
    links = group.links

    group_input = _new_node(nodes, "NodeGroupInput", _base_name("group_input"), -1800, 0)
    group_output = _new_node(nodes, "NodeGroupOutput", _base_name("group_output"), 10400, 0)
    set_position = _new_node(nodes, "GeometryNodeSetPosition", _base_name("set_position"), 10140, 0)
    position = _new_node(nodes, "GeometryNodeInputPosition", _base_name("position"), -1800, 300)

    self_object = _new_node(nodes, "GeometryNodeSelfObject", _base_name("self_object"), -1800, -340)
    object_info = _new_node(nodes, "GeometryNodeObjectInfo", _base_name("object_info"), -1580, -340)
    if hasattr(object_info, "transform_space"):
        object_info.transform_space = "ORIGINAL"

    world_scale = _new_vector_math(nodes, _base_name("world_scale"), "MULTIPLY", -1320, -160)
    world_rotate = _new_node(nodes, "ShaderNodeVectorRotate", _base_name("world_rotate"), -1100, -160)
    if hasattr(world_rotate, "rotation_type"):
        world_rotate.rotation_type = "EULER_XYZ"
    world_translate = _new_vector_math(nodes, _base_name("world_translate"), "ADD", -860, -160)

    sample_scale = _new_vector_math(nodes, _base_name("sample_scale"), "MULTIPLY", -640, 80)
    sample_scale_vector = _new_combine_xyz(nodes, _base_name("sample_scale_vector"), -880, 280, (1.0, 1.0, 1.0))
    global_seed = _new_combine_xyz(nodes, _base_name("global_seed"), -360, 300)
    global_seed_add = _new_vector_math(nodes, _base_name("global_seed_add"), "ADD", -120, 80)

    phase_value = _new_value(nodes, _base_name("phase_value"), -820, 620, 0.0)
    animate_value = _new_value(nodes, _base_name("animate_value"), -820, 780, 0.0)
    speed_value = _new_value(nodes, _base_name("speed_value"), -820, 940, 1.0)
    iterations_value = _new_value(nodes, _base_name("iterations_value"), -820, 1100, 4.0)
    roughness_value = _new_value(nodes, _base_name("roughness_value"), -820, 1260, 0.5)
    clamp_value = _new_value(nodes, _base_name("clamp_value"), -820, 1420, 2.5)

    scene_time = _new_node(nodes, "GeometryNodeInputSceneTime", _base_name("scene_time"), -1120, 940)
    time_multiply = _new_math(nodes, _base_name("time_multiply"), "MULTIPLY", -560, 940)
    time_enable = _new_math(nodes, _base_name("time_enable"), "MULTIPLY", -340, 940)
    phase_add = _new_math(nodes, _base_name("phase_add"), "ADD", -120, 780)

    links.new(_find_socket(group_input.outputs, "Geometry", 0), _find_socket(set_position.inputs, "Geometry", 0))
    links.new(_find_socket(set_position.outputs, "Geometry", 0), _find_socket(group_output.inputs, "Geometry", 0))

    links.new(_find_socket(self_object.outputs, "Self Object", 0), _find_socket(object_info.inputs, "Object", 0))
    links.new(_find_socket(position.outputs, "Position", 0), world_scale.inputs[0])
    links.new(_find_socket(object_info.outputs, "Scale", 3), world_scale.inputs[1])
    links.new(world_scale.outputs[0], _find_socket(world_rotate.inputs, "Vector", 0))
    links.new(_find_socket(object_info.outputs, "Rotation", 2), _find_socket(world_rotate.inputs, "Rotation", 4))
    links.new(_find_socket(world_rotate.outputs, "Vector", 0), world_translate.inputs[0])
    links.new(_find_socket(object_info.outputs, "Location", 1), world_translate.inputs[1])

    links.new(sample_scale_vector.outputs[0], sample_scale.inputs[1])
    links.new(sample_scale.outputs[0], global_seed_add.inputs[0])
    links.new(global_seed.outputs[0], global_seed_add.inputs[1])

    links.new(_find_socket(scene_time.outputs, "Seconds", 0), time_multiply.inputs[0])
    links.new(speed_value.outputs[0], time_multiply.inputs[1])
    links.new(time_multiply.outputs[0], time_enable.inputs[0])
    links.new(animate_value.outputs[0], time_enable.inputs[1])
    links.new(phase_value.outputs[0], phase_add.inputs[0])
    links.new(time_enable.outputs[0], phase_add.inputs[1])

    signed_outputs = []
    turbulence_outputs = []
    axis_origin_y = (1450, 200, -1050)
    for axis_index, axis_label in enumerate(AXIS_LABELS):
        signed_output, turbulence_output = _build_axis_output(
            nodes,
            links,
            global_seed_add.outputs[0],
            phase_add.outputs[0],
            roughness_value.outputs[0],
            iterations_value.outputs[0],
            axis_label,
            axis_index,
            260,
            axis_origin_y[axis_index],
        )
        signed_outputs.append(signed_output)
        turbulence_outputs.append(turbulence_output)

    combined_signed = _new_combine_xyz(nodes, _base_name("combined_signed"), 7640, 260)
    combined_turbulence = _new_combine_xyz(nodes, _base_name("combined_turbulence"), 7640, -140)
    strength = _new_combine_xyz(nodes, _base_name("strength"), 7900, 620, (0.25, 0.25, 0.25))
    final_multiply = _new_vector_math(nodes, _base_name("final_multiply"), "MULTIPLY", 8200, 80)
    final_separate = _new_node(nodes, "ShaderNodeSeparateXYZ", _base_name("final_separate"), 8480, 80)

    for index, socket in enumerate(signed_outputs):
        links.new(socket, combined_signed.inputs[index])
    for index, socket in enumerate(turbulence_outputs):
        links.new(socket, combined_turbulence.inputs[index])

    links.new(strength.outputs[0], final_multiply.inputs[1])
    links.new(final_multiply.outputs[0], final_separate.inputs[0])

    clamped_components = []
    clamp_rows = (280, 100, -80)
    for axis_label, component_socket, row in zip(AXIS_LABELS, final_separate.outputs, clamp_rows):
        clamped_components.append(
            _build_clamp_axis(
                nodes,
                links,
                component_socket,
                clamp_value.outputs[0],
                axis_label,
                8720,
                row,
            )
        )

    clamped_combine = _new_combine_xyz(nodes, _base_name("clamped_combine"), 9300, 80)
    for index, socket in enumerate(clamped_components):
        links.new(socket, clamped_combine.inputs[index])

    links.new(clamped_combine.outputs[0], _find_socket(set_position.inputs, "Offset", 3))

    return group


def ensure_noise_modifier(obj):
    settings = obj.max_noise_settings
    modifier = get_noise_modifier(obj)
    if modifier:
        modifier[MODIFIER_TAG] = True
        settings.modifier_name = modifier.name
        if modifier.node_group is None:
            modifier.node_group = build_node_group(_unique_group_name(obj))
        return modifier

    modifier = obj.modifiers.new(name=MODIFIER_NAME, type="NODES")
    modifier[MODIFIER_TAG] = True
    modifier.show_expanded = True
    modifier.node_group = build_node_group(_unique_group_name(obj))
    settings.modifier_name = modifier.name
    sync_modifier_from_object(obj)
    return modifier


def get_noise_modifier(obj):
    settings = getattr(obj, "max_noise_settings", None)
    if settings and settings.modifier_name:
        modifier = obj.modifiers.get(settings.modifier_name)
        if modifier and modifier.type == "NODES":
            return modifier

    for modifier in obj.modifiers:
        if modifier.type != "NODES":
            continue

        if modifier.get(MODIFIER_TAG):
            return modifier

        if modifier.name == MODIFIER_NAME:
            return modifier
    return None


def remove_noise_modifier(obj):
    modifier = get_noise_modifier(obj)
    if not modifier:
        return False

    group = modifier.node_group
    obj.max_noise_settings.modifier_name = ""
    obj.modifiers.remove(modifier)

    if group and group.users == 0:
        bpy.data.node_groups.remove(group)
    return True


def sync_modifier_from_object(obj):
    if obj is None or obj.type != "MESH":
        return

    modifier = get_noise_modifier(obj)
    if not modifier or modifier.node_group is None:
        return

    modifier[MODIFIER_TAG] = True
    obj.max_noise_settings.modifier_name = modifier.name

    if modifier.node_group.users > 1:
        modifier.node_group = modifier.node_group.copy()
        modifier.node_group.name = _unique_group_name(obj)

    group = modifier.node_group
    settings = obj.max_noise_settings
    nodes = group.nodes

    _set_combine_xyz(_node(nodes, _base_name("sample_scale_vector")), _effective_sample_scale(settings))
    _set_combine_xyz(_node(nodes, _base_name("global_seed")), _global_seed_offset(settings.seed))
    _set_combine_xyz(_node(nodes, _base_name("strength")), _effective_strength(settings))

    for axis_index, axis_label in enumerate(AXIS_LABELS):
        _set_combine_xyz(_node(nodes, _axis_seed_name(axis_label)), _axis_seed_offset(settings.seed, axis_index))

    _node(nodes, _base_name("phase_value")).outputs[0].default_value = settings.phase
    _node(nodes, _base_name("animate_value")).outputs[0].default_value = 1.0 if settings.animate_over_time else 0.0
    _node(nodes, _base_name("speed_value")).outputs[0].default_value = settings.animation_speed
    _node(nodes, _base_name("clamp_value")).outputs[0].default_value = settings.clamp_limit

    if settings.noise_type == "BASIC":
        iterations = 1.0
        roughness = 0.5
    else:
        iterations = float(min(settings.iterations, MAX_OCTAVES))
        roughness = settings.roughness

    _node(nodes, _base_name("iterations_value")).outputs[0].default_value = iterations
    _node(nodes, _base_name("roughness_value")).outputs[0].default_value = roughness

    sample_source = (
        _node(nodes, _base_name("world_translate")).outputs[0]
        if settings.space == "WORLD"
        else _node(nodes, _base_name("position")).outputs[0]
    )
    _relink(group, sample_source, _node(nodes, _base_name("sample_scale")).inputs[0])

    vector_source = (
        _node(nodes, _base_name("combined_turbulence")).outputs[0]
        if settings.noise_type == "TURBULENCE"
        else _node(nodes, _base_name("combined_signed")).outputs[0]
    )
    _relink(group, vector_source, _node(nodes, _base_name("final_multiply")).inputs[0])

    group.update_tag()
    obj.update_tag()


def _effective_sample_scale(settings):
    safe_size = max(settings.size, 1.0e-6)
    scale_xyz = settings.scale_xyz if settings.use_non_uniform_scale else (1.0, 1.0, 1.0)
    return tuple(max(component, 1.0e-6) / safe_size for component in scale_xyz)


def _effective_strength(settings):
    mask = (
        1.0 if settings.use_axis_x else 0.0,
        1.0 if settings.use_axis_y else 0.0,
        1.0 if settings.use_axis_z else 0.0,
    )
    return tuple(settings.strength[index] * mask[index] for index in range(3))


def _set_combine_xyz(node, values):
    node.inputs[0].default_value = values[0]
    node.inputs[1].default_value = values[1]
    node.inputs[2].default_value = values[2]


def _unique_group_name(obj):
    token = uuid.uuid4().hex[:8]
    return f"{NODE_GROUP_PREFIX}{obj.name}_{token}"
