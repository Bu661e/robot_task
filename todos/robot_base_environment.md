# robot_base_environment 任务清单

- [x] 创建模块文件 `robot/scenes/base_environment.py`
- [x] 实现基础环境中的桌子几何体
- [x] 实现 Franka 加载与桌边摆位
- [x] 实现顶视相机与基础灯光
- [x] 支持从 `robot/config.py` 读取全部手动配置
- [x] 兼容 Isaac Sim 5.0.0 返回的远程资产根路径解析
- [x] 修复 Franka 引用 prim 不兼容导致的平移未生效问题
- [x] 接入 Franka 拍照姿态默认关节配置
- [x] 让顶视相机优先对准桌面中央工作区
- [x] 将顶视相机注册为 Isaac `Camera` 传感器对象
