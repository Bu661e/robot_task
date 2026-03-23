from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias, TypedDict


# 公共 - 基础类型别名
# `Literal[...]` 表示字段只能取这些固定字面量值，而不是任意字符串。
Vec3: TypeAlias = list[float]
QuatWXYZ: TypeAlias = list[float]
Matrix3x3: TypeAlias = list[list[float]]
Matrix4x4: TypeAlias = list[list[float]]
BBoxXYXY: TypeAlias = list[int]

# FramePacket中的对象结构
class CameraInfo(TypedDict):
    intrinsic: Matrix3x3
    extrinsics_camera_to_world: Matrix4x4

# RobotContext中的对象结构
class APISpec(TypedDict):
    methods: list[str]

# PerceptionRequest中的对象结构
class FilePayload(TypedDict):
    file_name: str
    encoding: str
    content: str

# HTTP success response中的对象结构
class PerceptionObject(TypedDict):
    instance_id: str
    label: str
    object_mask_info: ObjectMaskInfo
    object_3d_info: Object3DInfo

# HTTP success response.objects中的对象结构
class ObjectMaskInfo(TypedDict):
    # `mask_files` 中对应 mask 的索引标识。
    mask_id: str
    score: float
    bbox_xyxy: BBoxXYXY

# HTTP success response.objects中的对象结构
class Object3DInfo(TypedDict):
    translation_m: Vec3
    rotation_wxyz: QuatWXYZ
    scale_m: Vec3
    extra: dict[str, object]

# PolicyRequest中的子结构
class PolicyTaskInput(TypedDict):
    task_id: str
    instruction: str
    object_texts: list[str]


#-------------------------------------------------------------------------

# M1 - `task_parser`
# input
class TaskRequest(TypedDict):
    task_id: str
    instruction: str


# output
class ParsedTask(TypedDict):
    task_id: str
    object_texts: list[str]


# M2 - `robot_bridge`
# output
class FramePacket(TypedDict):
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["camera"]
    rgb_path: str
    depth_path: str
    camera: CameraInfo


# output
class PointMapPacket(TypedDict):
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["camera"]
    point_map_path: str
    point_format: str


# M3 - `robot_config_provider`
# output
class RobotContext(TypedDict):
    coordinate_frame: Literal["world"]
    robot_name: str
    api_spec: APISpec


# M4 - `perception_client` 
#  HTTP input
class PerceptionRequest(TypedDict):
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["camera"]
    rgb_file: FilePayload
    point_map_file: FilePayload
    object_texts: list[str]


# HTTP output
class PerceptionResponseSuccess(TypedDict):
    success: Literal[True]
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["camera"]
    mask_files: list[FilePayload]
    objects: list[PerceptionObject]


# HTTP output
class PerceptionResponseFailure(TypedDict):
    success: Literal[False]
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["camera"]
    error: str


# HTTP output的统一类型
PerceptionResponse: TypeAlias = PerceptionResponseSuccess | PerceptionResponseFailure


# output
class CameraPerceptionResult(TypedDict):
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["camera"]
    objects: list[PerceptionObject]


# M5 - `pose_transformer`
# output
class WorldPerceptionResult(TypedDict):
    frame_id: str
    timestamp: str
    coordinate_frame: Literal["world"]
    objects: list[PerceptionObject]


# M6 - `policy_model`
# input
class PolicyRequest(TypedDict):
    task: PolicyTaskInput
    perception: WorldPerceptionResult
    robot_context: RobotContext


# output
class PolicyCode(TypedDict):
    language: Literal["python"]
    entrypoint: Literal["run"]
    code: str


# M7 - `policy_executor`
# output
class ExecutionResult(TypedDict):
    task_id: str
    success: bool
    selected_object_id: NotRequired[str]
    executed_api: NotRequired[str]
    message: str
