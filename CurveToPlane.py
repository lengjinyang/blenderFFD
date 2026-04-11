bl_info = {
    "name": "Curve Ribbon Pro",
    "author": "YourName",
    "version": (2, 1),
    "blender": (3, 0, 0),
    "location": "View3D > N-Panel > Tools",
    "description": "一键曲线旋转平面，并支持自定义曲线控制宽度变化",
    "category": "Curve",
}

import bpy
import math
from mathutils import Vector

# --- 1. 一键平躺操作符 ---
class CURVE_OT_MakeFlatRibbon(bpy.types.Operator):
    """将曲线挤出并平躺"""
    bl_idname = "curve.make_flat_ribbon"
    bl_label = "设置曲线旋转"
    bl_options = {'REGISTER', 'UNDO'}

    tilt_angle: bpy.props.FloatProperty(name="平躺角度 (度)", default=90.0)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'CURVE':
            return {'CANCELLED'}

        curve_data = obj.data
        curve_data.dimensions = '3D'
        
        if curve_data.extrude == 0:
            curve_data.extrude = 0.1
            
        rad_tilt = math.radians(self.tilt_angle)
        
        for spline in curve_data.splines:
            if spline.type == 'BEZIER':
                for pt in spline.bezier_points:
                    pt.tilt = rad_tilt
            elif spline.type in {'NURBS', 'POLY'}:
                for pt in spline.points:
                    pt.tilt = rad_tilt

        self.report({'INFO'}, "已旋转！")
        return {'FINISHED'}


# --- 2. 创建“宽度控制曲线”操作符 ---
class CURVE_OT_CreateTaper(bpy.types.Operator):
    """一键创建并分配宽度控制曲线 (锥化)"""
    bl_idname = "curve.create_taper"
    bl_label = "创建宽度控制曲线"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_obj = context.active_object
        if not target_obj or target_obj.type != 'CURVE':
            return {'CANCELLED'}

        # 1. 创建控制曲线数据
        taper_name = f"Width_Profile_{target_obj.name}"
        curve_data = bpy.data.curves.new(name=taper_name, type='CURVE')
        curve_data.dimensions = '2D' # 控制曲线必须是 2D 效果才好

        # 2. 写入点位数据 (两点一线，默认高度为 1.0 即 100% 宽度)
        spline = curve_data.splines.new('BEZIER')
        spline.bezier_points.add(1) # 默认有1个点，再加1个等于2个

        p0 = spline.bezier_points[0]
        p0.co = (-1.0, 1.0, 0.0)
        p0.handle_left = (-1.5, 1.0, 0.0)
        p0.handle_right = (-0.5, 1.0, 0.0)

        p1 = spline.bezier_points[1]
        p1.co = (1.0, 1.0, 0.0)
        p1.handle_left = (0.5, 1.0, 0.0)
        p1.handle_right = (1.5, 1.0, 0.0)

        # 3. 创建物体并放入场景
        taper_obj = bpy.data.objects.new(taper_name, curve_data)
        context.collection.objects.link(taper_obj)

        # 挪到原物体旁边 2 米处，防止重叠挡住视线
        taper_obj.location = target_obj.location + Vector((0, 2, 0))

        # 4. 指定给主曲线
        target_obj.data.taper_object = taper_obj

        self.report({'INFO'}, "宽度控制曲线已生成！")
        return {'FINISHED'}


# --- 3. 快速编辑控制曲线操作符 ---
class CURVE_OT_EditTaper(bpy.types.Operator):
    """快速跳转去编辑宽度"""
    bl_idname = "curve.edit_taper"
    bl_label = "修改宽度分布"
    
    def execute(self, context):
        target_obj = context.active_object
        taper_obj = target_obj.data.taper_object
        
        if taper_obj:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = taper_obj
            taper_obj.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'INFO'}, "请上下移动控制点来改变平面宽度 (Z轴被锁)")
        return {'FINISHED'}


# --- 4. 侧边栏 UI 面板 ---
class PANEL_PT_CurveTools(bpy.types.Panel):
    bl_label = "曲线转平面"
    bl_idname = "PANEL_PT_curve_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        if not obj or obj.type != 'CURVE':
            layout.label(text="请选择一条曲线", icon='CURVE_DATA')
            return

        # 模块一：平躺与基础宽度
        box = layout.box()
        box.label(text="1. 基础转换:", icon='MOD_THICKNESS')
        
        row = box.row()
        row.scale_y = 1.2
        op_flat = row.operator("curve.make_flat_ribbon", text="一键旋转 (90度)", icon='TRIA_DOWN_BAR')
        op_flat.tilt_angle = 90.0
        
        box.prop(obj.data, "extrude", text="基准宽度")

        layout.separator()

        # 模块二：宽度曲线控制
        box = layout.box()
        # 【修改了这里】把报错的 GP_CURVE 换成了安全的 CURVE_BEZCURVE 图标
        box.label(text="2. 分段调整宽度:", icon='CURVE_BEZCURVE')
        
        if not obj.data.taper_object:
            # 如果没有分配控制曲线，显示生成按钮
            box.label(text="当前平面首尾一样宽", icon='INFO')
            box.operator("curve.create_taper", text="生成宽度控制曲线", icon='MOD_CURVE')
        else:
            # 如果已经分配了控制曲线，显示编辑按钮
            box.prop(obj.data, "taper_object", text="控制对象")
            row = box.row()
            row.scale_y = 1.2
            row.operator("curve.edit_taper", text="去编辑宽度形状 (进入编辑)", icon='EDITMODE_HLT')
            
            box.label(text="提示: 曲线上下移动代表宽度变化", icon='LIGHT')

# --- 注册 ---
classes = (CURVE_OT_MakeFlatRibbon, CURVE_OT_CreateTaper, CURVE_OT_EditTaper, PANEL_PT_CurveTools)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()