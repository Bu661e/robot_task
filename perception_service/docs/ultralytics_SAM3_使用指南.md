# ultralytics SAM3 使用指南

本文档整理 `ultralytics` 包里 SAM3 的官方使用方式，重点区分它的几条接口到底分别适合什么场景，并给出适合当前 `perception_service` 的调用建议。

## 1. 先说结论：SAM3 在 ultralytics 里不是只有一种用法

同样是 `sam3.pt`，在 `ultralytics` 里至少有四条常用入口：

| 入口 | 适用对象 | 典型提示方式 | 适用场景 |
| --- | --- | --- | --- |
| `SAM("sam3.pt")` | 单张图 | 点、框、mask，或者无提示 | 找“这个位置上的这个物体” |
| `SAM3SemanticPredictor` | 单张图 | 文本、示例框 | 找“所有像瓶子/杯子/蓝色积木的实例” |
| `SAM3VideoPredictor` | 视频 | 点、框、mask | 在视频里跟踪指定实例 |
| `SAM3VideoSemanticPredictor` | 视频 | 文本、示例框 | 在视频里检测并持续跟踪某类目标 |

对我们当前项目最关键的是前两条：

- `SAM("sam3.pt")`
  - 更像 SAM2 风格的“交互式单实例分割”
- `SAM3SemanticPredictor`
  - 才是“概念分割 / 文本提示 / 示例提示 / 找所有匹配实例”的主入口

## 2. 安装和权重准备

### 2.1 安装版本

官方文档写的是：

- SAM3 在 `ultralytics >= 8.3.237` 可用

安装或升级命令：

```bash
pip install -U ultralytics
```

### 2.2 权重不会自动下载

这是和普通 YOLO 模型不一样的地方。官方文档明确说明：

- `sam3.pt` 不会自动下载
- 需要先去 Hugging Face 申请访问权限
- 然后自己下载权重文件

相关地址：

- 模型页：`https://huggingface.co/facebook/sam3`
- 权重文件：`https://huggingface.co/facebook/sam3/resolve/main/sam3.pt?download=true`

因此实际使用时更稳妥的写法是：

```python
model_path = "/absolute/path/to/sam3.pt"
```

不要假设 `ultralytics` 会像 YOLO 一样替你拉权重。

在当前机器上的固定约定是：

- 权重真实路径：`/root/sam3.pt`
- 仓库内使用的入口路径：`/root/robot_task/perception_service/sam3-ultralytics/sam3.pt`
- 这个入口路径应是一个软链接，指向 `/root/sam3.pt`

如果软链接丢失，可执行：

```bash
ln -s /root/sam3.pt /root/robot_task/perception_service/sam3-ultralytics/sam3.pt
```

### 2.3 `SimpleTokenizer` 报错时怎么修

官方文档还专门提到一个典型问题：

- `TypeError: 'SimpleTokenizer' object is not callable`

修法是：

```bash
pip uninstall clip -y
pip install git+https://github.com/ultralytics/CLIP.git
```

这说明 SAM3 的文本能力依赖正确版本的 CLIP，不要随便用环境里已有的 `clip` 包顶上。

## 3. `SAM("sam3.pt")` 适合什么

### 3.1 它的定位

`SAM("sam3.pt")` 对应的是 `ultralytics.models.sam.model.SAM`，在源码里会根据文件名自动识别这是 SAM3，然后加载交互式模型。

这条接口更适合：

- 你已经知道图上的大概位置
- 想用点、框或者已有 mask 提示模型
- 目标是“切出这个具体实例”

说明：

- 上面说的是 `SAM` 模型本身支持的提示方式
- 但在当前 `perception_service` 协议里，决策层不会上传 mask 作为输入
- 当前服务链路里实例 mask 由感知侧调用 SAM3 自己推理生成

不适合：

- 直接用文本找“所有 bottle”
- 直接做“所有与这个示例概念相似的对象”

### 3.2 最简单的视觉提示写法

```python
from ultralytics import SAM

model = SAM("/absolute/path/to/sam3.pt")

# 单点正样本提示
results = model.predict(
    source="path/to/image.jpg",
    points=[[900, 370]],
    labels=[1],
)

# 多点提示
results = model.predict(
    source="path/to/image.jpg",
    points=[[400, 370], [900, 370]],
    labels=[1, 1],
)

# 框提示
results = model.predict(
    source="path/to/image.jpg",
    bboxes=[[100, 150, 300, 400]],
)
```

这里有几个源码层面的细节：

- `points` 坐标使用原图像素坐标
- `labels`
  - `1` 表示前景点
  - `0` 表示背景点
- `bboxes` 使用 `xyxy`
- 如果只传一个点或一个框，也最好用二维列表包起来

### 3.3 不传提示会发生什么

如果你对 `SAM("sam3.pt")` 什么提示都不传，它不会报错，而是走“全图自动分割”逻辑，也就是源码里的 `generate()`：

```python
results = model.predict(source="path/to/image.jpg")
```

这会尝试产出整张图的一批 mask。对我们的 `perception_service` 来说，这通常不是首选，因为：

- mask 数量可能很多
- 语义不明确
- 后面要接 3D 重建时成本太高

所以对机器人任务而言，更推荐：

- 有精确点击/框时，用 `SAM`
- 有语义目标时，用 `SAM3SemanticPredictor`

### 3.4 默认参数里有哪些要知道的事

从源码看，`SAM.predict()` 会默认带上：

- `conf=0.25`
- `task="segment"`
- `mode="predict"`
- `imgsz=1024`

也就是说如果你不主动传 `imgsz`，SAM3 这条路径默认按 `1024` 方图来做预处理。

## 4. `SAM3SemanticPredictor` 才是文本/概念分割主入口

### 4.1 它和 `SAM` 的本质区别

`SAM3SemanticPredictor` 不是“把 `SAM` 换个名字”，而是另一条预测器路径。

从官方文档和源码看，它的核心能力是：

- 文本概念分割
- 示例框驱动的概念分割
- 一次提取图像特征，多次复用

最重要的一句话可以这样记：

- `SAM("sam3.pt")`
  - 找“这个位置上的这个物体”
- `SAM3SemanticPredictor`
  - 找“所有符合这个概念的物体”

### 4.2 文本提示用法

```python
from ultralytics.models.sam import SAM3SemanticPredictor

overrides = dict(
    conf=0.25,
    task="segment",
    mode="predict",
    model="/absolute/path/to/sam3.pt",
    half=True,
    save=False,
    verbose=False,
)

predictor = SAM3SemanticPredictor(overrides=overrides)

# 先固定图像
predictor.set_image("path/to/image.jpg")

# 再做多次文本查询
results = predictor(text=["person", "bus", "glasses"])
results = predictor(text=["blue bottle", "red cup"])
results = predictor(text=["a person"])
```

有几个细节需要注意：

- `set_image()` 会先把图像特征提出来缓存起来
- 后面你可以在同一张图上多次换 `text`
- 文本既可以是名词，也可以是描述性短语

对我们的抓取任务，这条能力很有价值，因为：

- `task_parser` 解析出的 `object_texts`
- 可以直接作为 `text` 提示输入进去

### 4.3 示例框用法

```python
from ultralytics.models.sam import SAM3SemanticPredictor

overrides = dict(
    conf=0.25,
    task="segment",
    mode="predict",
    model="/absolute/path/to/sam3.pt",
    half=True,
    save=False,
    verbose=False,
)

predictor = SAM3SemanticPredictor(overrides=overrides)
predictor.set_image("path/to/image.jpg")

results = predictor(bboxes=[[480.0, 290.0, 590.0, 650.0]])
results = predictor(bboxes=[[539, 599, 589, 639], [343, 267, 499, 662]])
```

这条路径的语义不是“只把这个框里的物体切出来”，而是：

- 把这个框当作视觉 exemplar
- 在整张图里找所有视觉上相似的实例

源码里还有一个关键实现细节：

- 如果你只传 `bboxes`，不传 `text`
- 它会自动塞一个占位文本 `visual`

所以这条接口本质上还是概念分割，只不过概念来源不是文字，而是示例框。

### 4.4 同一张图复用特征

如果你要在一张图上连续问多个概念，不要每次都重新编码图像。

官方示例对应的复用方式是：

```python
import cv2

from ultralytics.models.sam import SAM3SemanticPredictor

overrides = dict(
    conf=0.50,
    task="segment",
    mode="predict",
    model="/absolute/path/to/sam3.pt",
    verbose=False,
)

predictor = SAM3SemanticPredictor(overrides=overrides)
predictor2 = SAM3SemanticPredictor(overrides=overrides)

source = "path/to/image.jpg"
predictor.set_image(source)
src_shape = cv2.imread(source).shape[:2]

predictor2.setup_model()

masks, boxes = predictor2.inference_features(
    predictor.features,
    src_shape=src_shape,
    text=["person"],
)
```

这在我们的 `perception_service` 里尤其合适，因为同一帧里通常会对多个 `object_texts` 连续查询。

## 5. `SAM3SemanticPredictor` 的几个源码级细节

这些点官方文档提到了部分，但源码里更清楚。

### 5.1 它不支持图像 batch

源码里直接写了：

- `assert len(im) == 1`

也就是说：

- 它可以在一张图上做多 concept 查询
- 但当前不适合一次塞多张图

### 5.2 `set_image()` 的输入格式

`set_image()` 支持两种常见输入：

- 图片路径字符串
- `cv2.imread()` 读出来的 `numpy.ndarray`

而且文档明确说这里的数组按 `cv2` 习惯处理，也就是默认是 BGR。

### 5.3 框坐标约定

`SAM3SemanticPredictor` 对外仍然使用原图像素坐标的 `xyxy` 框。

但它内部会做两步转换：

1. 把 `xyxy` 转成 `xywh`
2. 再按图像宽高归一化

所以外部调用层不要自己先归一化，直接传原图像素坐标即可。

### 5.4 返回结果

常规 `predictor(...)` 路径返回的是 `Results` 对象列表，里面最常用的字段通常是：

- `results[0].masks.data`
- `results[0].boxes.xyxy`
- `results[0].boxes.conf`
- `results[0].boxes.cls`

如果你走的是 `inference_features()`，返回的是：

- `pred_masks`
- `pred_bboxes`

这条路径返回 tensor，不是 `Results` 包装对象。

## 6. 视频接口什么时候用

### 6.1 `SAM3VideoPredictor`

适合：

- 视频输入
- 有点/框/mask 这样的视觉提示
- 目标是持续跟踪指定实例

```python
from ultralytics.models.sam import SAM3VideoPredictor

overrides = dict(
    conf=0.25,
    task="segment",
    mode="predict",
    model="/absolute/path/to/sam3.pt",
    half=True,
)

predictor = SAM3VideoPredictor(overrides=overrides)
results = predictor(
    source="path/to/video.mp4",
    bboxes=[[706.5, 442.5, 905.25, 555]],
    stream=True,
)

for r in results:
    r.show()
```

### 6.2 `SAM3VideoSemanticPredictor`

适合：

- 视频输入
- 用文本或示例框做概念级检测和跟踪

```python
from ultralytics.models.sam import SAM3VideoSemanticPredictor

overrides = dict(
    conf=0.25,
    task="segment",
    mode="predict",
    imgsz=640,
    model="/absolute/path/to/sam3.pt",
    half=True,
    save=False,
)

predictor = SAM3VideoSemanticPredictor(overrides=overrides)
results = predictor(
    source="path/to/video.mp4",
    text=["person", "bicycle"],
    stream=True,
)

for r in results:
    r.show()
```

这条预测器内部做的事情比单图复杂很多：

- 会维护视频级 `inference_state`
- 首帧根据提示建立对象
- 后续帧继续传播和更新 masklet

对当前机器人抓取任务来说，除非你要做连续视频感知，否则先不用急着上这条路径。

## 7. 对当前 `perception_service` 的推荐用法

### 7.1 如果输入是自然语言目标

例如：

- `"pick the bottle"`
- `"move the blue block"`

推荐：

- 用 `SAM3SemanticPredictor`
- 直接传 `text=["bottle"]`、`text=["blue block"]`

这样得到的是“所有匹配实例”的 mask 候选。

### 7.2 如果输入是人为点击或已有像素位置

例如：

- UI 上点了一下某个物体
- 上游模块已经给了一个 bbox

推荐：

- 用 `SAM("sam3.pt")`
- 用点或框做视觉提示

这样语义最清楚，分割也最稳定。

### 7.3 如果你已经有一个 exemplar 框

例如：

- 先框住一个已知杯子
- 再找整图里类似的杯子

推荐：

- 用 `SAM3SemanticPredictor(bboxes=...)`

这比普通 `SAM` 更符合“找所有类似实例”的目标。

### 7.4 和 `SAM3D-object` 怎么串

推荐串法：

1. 用 `SAM3SemanticPredictor` 或 `SAM` 先得到 2D mask
2. 从 `results[0].masks.data` 里逐个取出实例 mask
3. 每个实例单独喂给 `SAM3D-object`
4. 得到每个实例的 3D 位姿和形状

不要反过来指望 `SAM3D-object` 自己做文本分割。

## 8. 一个更贴近当前项目的最小示例

下面这个例子更接近我们之后会在 `perception_service` 里做的事情：

```python
from ultralytics.models.sam import SAM3SemanticPredictor

overrides = dict(
    conf=0.25,
    task="segment",
    mode="predict",
    model="/absolute/path/to/sam3.pt",
    half=True,
    verbose=False,
)

predictor = SAM3SemanticPredictor(overrides=overrides)
predictor.set_image("/path/to/rgb.png")

results = predictor(text=["bottle"])

r = results[0]
masks = r.masks.data.cpu().numpy() if r.masks is not None else []
boxes = r.boxes.xyxy.cpu().numpy() if r.boxes is not None else []

for idx, mask in enumerate(masks):
    # 这里把 mask 继续送进 SAM3D-object
    # output_3d = sam3d_inference(image_rgb, mask, pointmap=pointmap)
    print(idx, boxes[idx])
```

这个模式基本就是：

- 文本找 2D
- mask 驱动 3D

## 9. 当前最值得记住的几个坑

### 9.1 `SAM("sam3.pt")` 不做文本概念分割

它是视觉提示接口，不是概念分割主接口。

### 9.2 文本分割要用 `SAM3SemanticPredictor`

如果你要找“所有 bottle”，要走 semantic predictor，不要走 `SAM`。

### 9.3 权重不自动下载

这一点和 YOLO 常规模型不同，部署脚本里必须显式处理。

### 9.4 CLIP 版本不对会炸

如果文本推理报 `SimpleTokenizer` 相关错误，优先查 `clip` 包版本。

### 9.5 当前不支持图像 batch

同一张图上多次查询没问题，但多图 batch 不是当前最合适的调用形态。

## 10. 参考链接

- 官方文档：`https://docs.ultralytics.com/models/sam-3/`
- 官方源码入口：`https://github.com/ultralytics/ultralytics/blob/main/ultralytics/models/sam/model.py`
- 官方预测器源码：`https://github.com/ultralytics/ultralytics/blob/main/ultralytics/models/sam/predict.py`
- Hugging Face 权重页：`https://huggingface.co/facebook/sam3`
