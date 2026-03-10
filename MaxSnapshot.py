bl_info = {
    "name": "Max Style Snapshot",
    "author": "YourName",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > N-Panel > Tools",
    "description": "类似 3ds Max 的 Snapshot 功能，一键烘焙动画/修改器形变并生成网格副本",
    "category": "Object",
}

import bpy

class OBJECT_OT_MaxSnapshot(bpy.types.Operator):
    """类似 3ds Max 的快照工具"""
    bl_idname = "object.max_snapshot"
    bl_label = "快照 (Snapshot)"
    bl_options = {'REGISTER', 'UNDO'}

    # --- 弹窗参数 ---
    snapshot_mode: bpy.props.EnumProperty(
        name="快照模式",
        description="选择生成单帧还是一个时间段内的多个快照",
        items=[
            ('SINGLE', "单帧 (Single)", "仅捕获当前帧"),
            ('RANGE', "范围 (Range)", "在时间轴范围内生成多个快照"),
        ],
        default='SINGLE'
    )

    start_frame: bpy.props.IntProperty(name="起始帧", default=1)
    end_frame: bpy.props.IntProperty(name="结束帧", default=100)
    copies: bpy.props.IntProperty(name="克隆数量", default=10, min=2)
    
    # 记录执行前的当前帧，方便恢复
    original_frame: int = 0

    def invoke(self, context, event):
        # 唤起时自动获取当前时间轴的范围作为默认值
        self.start_frame = context.scene.frame_start
        self.end_frame = context.scene.frame_end
        # 调出弹窗
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "snapshot_mode", expand=True) # expand=True 会显示为两个并排按钮
        
        # 如果是范围模式，才显示下方参数
        if self.snapshot_mode == 'RANGE':
            box = layout.box()
            box.prop(self, "start_frame")
            box.prop(self, "end_frame")
            box.prop(self, "copies")

    def execute(self, context):
        source_obj = context.active_object
        scene = context.scene

        # 1. 检查选中物体
        if not source_obj or source_obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
            self.report({'ERROR'}, "请先选择一个包含几何体数据的物体 (网格/曲线/文字)")
            return {'CANCELLED'}

        self.original_frame = scene.frame_current

        # 2. 为快照创建一个新的集合 (保持项目整洁)
        col_name = f"{source_obj.name}_Snapshots"
        if col_name not in bpy.data.collections:
            snap_col = bpy.data.collections.new(col_name)
            scene.collection.children.link(snap_col)
        else:
            snap_col = bpy.data.collections[col_name]

        # 3. 核心抓取函数
        def create_snapshot_at_current_frame(frame_num):
            # 获取当前帧的依赖图 (包含修改器/动画的最终结算结果)
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = source_obj.evaluated_get(depsgraph)
            
            # 从结算结果直接生成新的纯网格数据
            new_mesh = bpy.data.meshes.new_from_object(eval_obj)
            
            # 创建新物体
            new_obj = bpy.data.objects.new(f"{source_obj.name}_Snap_F{int(frame_num)}", new_mesh)
            
            # 复制世界矩阵 (捕获物体的位移/旋转/缩放动画)
            new_obj.matrix_world = eval_obj.matrix_world.copy()
            
            # 放入集合
            snap_col.objects.link(new_obj)

        # 4. 根据模式执行
        if self.snapshot_mode == 'SINGLE':
            # 直接抓取当前帧
            create_snapshot_at_current_frame(self.original_frame)
            self.report({'INFO'}, f"已生成帧 {self.original_frame} 的快照")

        elif self.snapshot_mode == 'RANGE':
            # 计算步长
            step = (self.end_frame - self.start_frame) / (self.copies - 1)
            frames_to_capture =[self.start_frame + i * step for i in range(self.copies)]
            
            for f in frames_to_capture:
                # 跳转时间轴
                scene.frame_set(int(f))
                # 强制刷新视图层以更新修改器和骨骼
                context.view_layer.update()
                # 抓取
                create_snapshot_at_current_frame(f)
            
            # 恢复初始帧
            scene.frame_set(self.original_frame)
            self.report({'INFO'}, f"成功生成 {self.copies} 个快照")

        return {'FINISHED'}


# --- 将按钮添加到 N 键侧边栏 ---
class PANEL_PT_MaxTools(bpy.types.Panel):
    bl_label = "Max Tools"
    bl_idname = "PANEL_PT_max_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tools" 

    def draw(self, context):
        layout = self.layout
        
        # 呼出快照弹窗的按钮
        op = layout.operator("object.max_snapshot", text="快照 (Snapshot)", icon='RENDER_STILL')
        # 这里把按钮弄大一点，符合重要工具的感觉
        op_scale = layout.column()
        op_scale.scale_y = 1.2

# --- 注册 ---
classes = (
    OBJECT_OT_MaxSnapshot,
    PANEL_PT_MaxTools,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()