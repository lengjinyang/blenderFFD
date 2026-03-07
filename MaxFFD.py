bl_info = {
    "name": "Super FFD (Max Style)",
    "author": "YourName",
    "version": (4, 0),
    "blender": (3, 0, 0),
    "location": "View3D > N-Panel > Tools",
    "description": "集成了绑定控制的实时 FFD 工具",
    "category": "Object",
}

import bpy
import bmesh
from mathutils import Vector

# --- 核心逻辑：生成/更新笼子网格 ---
def update_ffd_cage(self, context):
    """当属性改变时自动触发此函数"""
    target_obj = context.object
    
    # 安全检查
    if not target_obj or not target_obj.ffd_target_cage:
        return

    # 如果已经绑定，禁止修改网格，防止崩溃或逻辑错误
    mod = target_obj.modifiers.get("FFD_Live")
    if mod and mod.is_bound:
        return 

    cage_obj = target_obj.ffd_target_cage
    props = target_obj.ffd_props

    # 1. 确保在物体模式
    if context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # 2. 计算笼子尺寸 (基于原物体包围盒)
    bbox = [target_obj.matrix_world @ Vector(corner) for corner in target_obj.bound_box]
    min_v = Vector((min([v.x for v in bbox]), min([v.y for v in bbox]), min([v.z for v in bbox])))
    max_v = Vector((max([v.x for v in bbox]), max([v.y for v in bbox]), max([v.z for v in bbox])))
    
    center = (min_v + max_v) / 2
    dims = max_v - min_v
    
    size_x = dims.x * props.padding
    size_y = dims.y * props.padding
    size_z = dims.z * props.padding
    
    res_x = max(2, props.res_x)
    res_y = max(2, props.res_y)
    res_z = max(2, props.res_z)

    # 3. 使用 BMesh 重建网格
    bm = bmesh.new()
    
    # 生成底面 Grid
    bmesh.ops.create_grid(bm, x_segments=res_x-1, y_segments=res_y-1, size=0.5)
    bmesh.ops.scale(bm, vec=Vector((size_x, size_y, 1.0)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, 0, -size_z/2)), verts=bm.verts)
    
    # 挤出
    extrude = bmesh.ops.extrude_face_region(bm, geom=bm.faces)
    verts_extruded = [e for e in extrude['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, size_z)), verts=verts_extruded)
    
    # Z轴细分
    if res_z > 2:
        edges_vertical = []
        for e in bm.edges:
            v1, v2 = e.verts
            if abs((v1.co - v2.co).z) > size_z * 0.9:
                edges_vertical.append(e)
        bmesh.ops.subdivide_edges(bm, edges=edges_vertical, cuts=res_z-2, use_grid_fill=True)
    
    bm.to_mesh(cage_obj.data)
    bm.free()
    
    # 更新位置
    cage_obj.location = center
    cage_obj.rotation_euler = (0,0,0)
    cage_obj.scale = (1,1,1)

# --- 属性组 ---
class FFD_Props(bpy.types.PropertyGroup):
    res_x: bpy.props.IntProperty(name="X", default=2, min=2, max=32, update=update_ffd_cage)
    res_y: bpy.props.IntProperty(name="Y", default=2, min=2, max=32, update=update_ffd_cage)
    res_z: bpy.props.IntProperty(name="Z", default=2, min=2, max=32, update=update_ffd_cage)
    padding: bpy.props.FloatProperty(name="间距", default=1.1, min=1.01, max=3.0, update=update_ffd_cage)
    precision: bpy.props.IntProperty(name="精度", default=5, min=2, max=10)

# --- 操作符：初始化 ---
class OBJECT_OT_InitFFD(bpy.types.Operator):
    """初始化 FFD"""
    bl_idname = "object.ffd_init"
    bl_label = "初始化 FFD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "请选择网格物体")
            return {'CANCELLED'}
        
        # 清理旧笼子
        if obj.ffd_target_cage:
            try:
                bpy.data.objects.remove(obj.ffd_target_cage, do_unlink=True)
            except:
                pass
        
        # 创建新笼子
        me = bpy.data.meshes.new(f"Cage_{obj.name}")
        cage = bpy.data.objects.new(f"Cage_{obj.name}", me)
        context.collection.objects.link(cage)
        cage.display_type = 'WIRE'
        cage.hide_render = True
        
        obj.ffd_target_cage = cage
        update_ffd_cage(None, context)
        
        # 添加修改器
        mod = obj.modifiers.get("FFD_Live")
        if not mod:
            mod = obj.modifiers.new(name="FFD_Live", type='MESH_DEFORM')
        mod.object = cage
        
        return {'FINISHED'}

# --- 操作符：绑定/解绑 ---
class OBJECT_OT_ToggleBind(bpy.types.Operator):
    """绑定或解绑 Mesh Deform"""
    bl_idname = "object.ffd_toggle_bind"
    bl_label = "绑定/解绑"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.StringProperty(default="BIND") # BIND or UNBIND

    def execute(self, context):
        obj = context.active_object
        mod = obj.modifiers.get("FFD_Live")
        
        if not mod:
            self.report({'ERROR'}, "未找到修改器")
            return {'CANCELLED'}

        # 确保物体是活动的
        context.view_layer.objects.active = obj
        
        if self.action == "BIND":
            mod.precision = obj.ffd_props.precision
            try:
                bpy.ops.object.meshdeform_bind(modifier="FFD_Live")
                self.report({'INFO'}, "FFD 已绑定！")
            except RuntimeError:
                self.report({'ERROR'}, "绑定失败，检查模型是否闭合")
        
        elif self.action == "UNBIND":
            # Blender 的 Unbind 操作其实是同一个 ops，只是名字叫 unbind
            # 实际上 meshdeform_bind 按钮在已绑定时会变成 Unbind，
            # 调用同样的 operator 会执行解绑。
            try:
                bpy.ops.object.meshdeform_bind(modifier="FFD_Live")
                self.report({'INFO'}, "FFD 已解绑，可修改参数")
            except RuntimeError:
                pass

        return {'FINISHED'}

# --- 操作符：快速进入编辑 ---
class OBJECT_OT_EditCage(bpy.types.Operator):
    """选中笼子并进入编辑模式"""
    bl_idname = "object.ffd_edit_cage"
    bl_label = "编辑笼子"
    
    def execute(self, context):
        obj = context.active_object
        cage = obj.ffd_target_cage
        if cage:
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = cage
            cage.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

# --- 面板 UI ---
class PANEL_PT_SuperFFD(bpy.types.Panel):
    bl_label = "Super FFD"
    bl_idname = "PANEL_PT_super_ffd"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tools" 

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        if not obj or obj.type != 'MESH':
            layout.label(text="请选择网格物体")
            return

        # 1. 还没有初始化 -> 显示初始化按钮
        if not obj.ffd_target_cage:
            layout.operator("object.ffd_init", text="创建 FFD", icon='MESH_CUBE')
        else:
            # 获取修改器状态
            mod = obj.modifiers.get("FFD_Live")
            is_bound = mod.is_bound if mod else False
            props = obj.ffd_props

            # 2. 参数区
            box = layout.box()
            box.label(text="参数调整:", icon='PREFERENCES')
            
            # 如果已绑定，禁用参数修改
            col = box.column()
            col.enabled = not is_bound # 关键：绑定后变灰
            
            row = col.row(align=True)
            row.prop(props, "res_x")
            row.prop(props, "res_y")
            row.prop(props, "res_z")
            col.prop(props, "padding")
            col.prop(props, "precision")

            layout.separator()

            # 3. 绑定/解绑按钮区
            if is_bound:
                # 状态：已绑定
                row = layout.row()
                row.alert = True # 红色警告色，提示这是解绑
                op = row.operator("object.ffd_toggle_bind", text="解绑 (Unbind)", icon='X')
                op.action = "UNBIND"
                
                # 编辑按钮 (大号)
                row = layout.row()
                row.scale_y = 1.5
                row.operator("object.ffd_edit_cage", text="开始变形 (进入编辑模式)", icon='EDITMODE_HLT')
                
            else:
                # 状态：未绑定
                row = layout.row()
                row.scale_y = 1.5 # 大按钮
                op = row.operator("object.ffd_toggle_bind", text="绑定 (Bind)", icon='LINKED')
                op.action = "BIND"
                
                row = layout.row()
                layout.label(text="调整好参数后点击绑定", icon='INFO')

# --- 注册 ---
classes = (
    FFD_Props,
    OBJECT_OT_InitFFD,
    OBJECT_OT_ToggleBind,
    OBJECT_OT_EditCage,
    PANEL_PT_SuperFFD,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.ffd_props = bpy.props.PointerProperty(type=FFD_Props)
    bpy.types.Object.ffd_target_cage = bpy.props.PointerProperty(type=bpy.types.Object)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Object.ffd_props
    del bpy.types.Object.ffd_target_cage

if __name__ == "__main__":
    register()