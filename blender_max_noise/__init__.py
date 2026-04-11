bl_info = {
    "name": "Max Noise Modifier",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Properties > Modifiers",
    "description": "3ds Max style procedural noise deformation using Geometry Nodes",
    "category": "Object",
}

from . import operators, properties, ui


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
