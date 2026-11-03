# 图书馆现场演示：只推理，不训练

本版本保留原 README 和完整研究代码，增加独立的 `showcase` 入口。现场使用已训练好的公开任务头，对预先准备的图书馆观测重新前向推理。训练命令仍供研究复现使用，但不属于演示流程。

## 本机演示

双击项目根目录 `START_SHOWCASE.cmd`，打开本地三栏工作台。左栏选择或拖入文件，中栏启动推理并查看真实日志和代码，右栏预览几何、下载结果或调用 SketchUp。保持服务终端开启，浏览器访问 `http://127.0.0.1:8765`。

```powershell
python tools/run_showcase_web.py --open
# 或：python -m zip2cad showcase-web --open
```

### 网页输入区

| 输入 | 用途 | 是否现场必选 |
| --- | --- | --- |
| 图书馆预处理案例 ZIP | 观测网格、点云、坐标契约及原始/成品 SKP | 必需；已装案例包时可直接使用内置示例 |
| 原始图书馆 SKP | 原图对比及本次预测 SKP 写入 | 可替换，必须匹配案例坐标和对象层级 |
| 完整校园成品 SKP | 预先完成的最终模型展示 | 可替换，默认使用本项目准备的成品 |
| 原始视频 | 播放实景，解释观测来源 | 可选，仅供讲解，不进入本次快速任务头推理 |

原始材料仍然是实景视频和原始 SKP，但这套现场模式从预处理观测开始。只上传视频和 SKP，不能替代案例 ZIP，也不会自动运行整段 ZipMap 重建。浏览器选择的文件会复制到本地 `outputs/web/uploads/`，不上传到云端。原文件不被覆盖；每次推理另建独立目录。

### 三维预览和 SketchUp

网页通过官方 SDK 提取实际 SKP 网格，再由本地 WebGL 查看器显示，可拖动旋转、滚轮缩放。原始图书馆、本次现场预测、校园成品图书馆局部分别可切换。

网页使用基础材质色，不还原摄影纹理；完整校园、SketchUp 场景和编辑请点「用 SketchUp 打开」。这会调用 Windows 中 `.skp` 的默认关联程序。未检测到 SDK 时，仍可显示现场预测几何和导出 OBJ；原始/成品 SKP 使用 SketchUp 查看。替换为其它校园模型时，内置图书馆 PID 范围可能不匹配，预览失败会提示改用原软件。

网页服务只监听本机回环地址，默认端口 8765；可用 `--port 8766` 换端口。参数区显示实际网络契约，代码区为实际执行函数的只读源代码；没有可执行的网页代码编辑框。现场预测与预先保存的成品始终明确区分。

### 保留的命令行入口

双击 `START_SHOWCASE_CLI.cmd`，打开项目目录下已激活本机 `.venv` 的命令行窗口。**每一步都是独立的 Python 程序**，完成后退出到终端，不会自动执行下一步。按讲解节奏逐条输入：

```powershell
python step1.py
python step2.py
python step3.py
python step4.py
python step5.py
```

| 命令 | 实际工作 |
| --- | --- |
| `python step1.py` | 输入、契约、预训练权重校验；新建一次运行目录 |
| `python step2.py` | 从已保存观测重新执行几何和六角点网络，保存预测 JSON |
| `python step3.py` | 导出 OBJ、预测图；有 SDK 时新建预测 SKP 并保存重读校验 |
| `python step4.py` | 校验并复制准备好的完整校园成品，不把它作为现场网络输出 |
| `python step5.py` | 检查前四步产物、汇总运行报告、显示产物文件夹菜单 |

每个入口只有几行，实际函数在 `src/zip2cad/showcase_steps.py`。完整日志分别保存为 `step1.log` 至 `step5.log`，状态和产物哈希记录在 `stepwise_run.json`；当前运行位置记录在 `outputs/current_stepwise_run.json`。前置步骤未完成、数据或权重被改动时，下一条命令明确报错，不会静默重新计算。

重新演示：完整五步完成后，再执行 `python step1.py` 会新建运行目录。若要放弃未完成的一次运行并另开一次，输入 `python step1.py --new-run`。原目录和结果不删除。第三步失败后，可修复环境再重跑第三步。

`python step1.py --skp off` 可明确禁用本次运行的原生 SKP 写入；`--skp required` 要求必须有 SDK。`python step5.py --no-menu` 可在检查完成后直接返回终端，便于自动验证。

CLI 的步骤、键盘操作、取消、错误及文件夹菜单提示统一使用英文。完成后出现 `[0] Open output folder`，输入数字 **0** 并按 Enter 打开产物目录。

当前启动脚本不执行固定时长、自动倒计时或网页跳转，终端不输出 `PRESENTATION HOLD`。节奏由逐条输入命令控制；总时长取决于计算和讲解时间。`run_report.json` 记录实际任务头推理时间及已完成阶段。

完成后控制台给出实际产物文件夹路径。输入**数字 0，再按 Enter**打开该文件夹；输入 **Q，再按 Enter**退出。兼容字母 O，但推荐数字 0，避免混淆。用 SketchUp 打开 `campus_final_showcase.skp` 展示完整校园成品；`live_predicted_library.skp` 是本次现场预测生成的图书馆（有 SDK 时）。原网页入口仍单独保留。

```powershell
# 原来的 Enter 确认式单进程入口仍可显式使用：
python tools/run_showcase.py --verbose --step-by-step --folder-menu
# 自动执行五步，只输出详细真实日志：
python tools/run_showcase.py --verbose --presentation-seconds 0
```

也保留原来的简洁命令（只有显式 `--open` 才打开结果网页）：

```powershell
python tools/run_showcase.py --open
# 等价的包入口（已安装本项目时）：
python -m zip2cad showcase --open
```

现场五步：校验观测与模型 → 现场几何/六角点推理 → 导出预测并可视化 → 输出完整校园成品 → 打开结果和运行记录。

不调用训练、不更新权重、不现场重新跑整段 ZipMap，也不重新提取 Sonata 特征。推理前准备好的输入是观测网格与点云，不是房体/风管参数或 ABCDEF 预测答案。两个任务头每次都会重新执行 `eval()` / `torch.inference_mode()`。

## 展示顺序与项目价值

1. **解释输入**：视频经 ZipMap 转为有坐标的观测，再用冻结特征、语义和已有 CAD 轮廓组成 15 通道网格；本例提前保存这些耗时的预处理结果。
2. **现场推理**：在终端展示任务头加载与运行，在结果页查看本次计算的房体、两条风管和 ABCDEF 六角点。
3. **可编辑几何**：展示 `predicted_geometry.obj`；安装官方 SDK 时，程序还会输出 `live_predicted_library.skp`，通过保存重读校验。该文件来自本次预测，保留原图书馆 CAD。
4. **完整校园成品**：打开 `campus_final_showcase.skp` 展示用户选定的完整校园交付模型。
5. **可追溯性**：查看 `run_report.json` 的输入/权重 SHA256、现场推理用时和执行范围。

应向导师准确区分：**现场任务头预测**与**预先保存的完整校园成品**。完整校园的梁架、立柱、照片约束细节和其它建筑不是这两个任务头当场生成的；成品文件不参与预测。当前任务头来自同一图书馆开发案例，不宣称独立建筑泛化精度。

## 新电脑 / GitHub 访客

建议 Python 3.11。先安装项目，再将图书馆案例数据包解压到项目根目录：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[neural]"
# 将 Zip2CAD1.0-Showcase-library-demo.zip 解压到这里后：
.venv\Scripts\python tools/run_showcase.py --open
```

基础演示只需要 CPU，不下载 ZipMap/Sonata 骨干，不需要 CUDA。原生预测 SKP 另需官方 SketchUp C SDK；已安装 SketchUp 时自动查找，否则可设置 `ZIP2CAD_SKETCHUP_SDK`。没有 SDK 仍能完成现场预测、OBJ、图像、日志和完整校园成品输出，结果日志会明确记录跳过原生预测 SKP。

```powershell
# 要求原生预测 SKP，缺 SDK 就明确报错：
python tools/run_showcase.py --skp required --open
# 明确只做网络推理及便携导出：
python tools/run_showcase.py --skp off --open
```

## 案例数据与发布

源码包包含三个公开任务头和演示程序。图书馆观测、原始 CAD 及选定的完整校园成品放在单独的案例 ZIP 中；`artifacts/` 不进入 Git。发布时将案例 ZIP 放到同一个 GitHub Release，说明解压位置，不能只发布源码却声称包含可直接运行的案例。

案例目录结构：

```text
artifacts/showcase/library/
  manifest.json
  joint_inputs/all.npz
  joint_inputs/input_contract.json
  corner_inputs.npz
  corner_contract.json
  original_library.skp
  campus_final.skp
```

作者准备或更换数据包时使用（提供自己的实际路径）：

```powershell
python tools/prepare_showcase_case.py --library-case artifacts/library1.0 --original-cad data/raw/library/original.skp --final-model data/deliverables/whole_school_detailed_revision.skp --output artifacts/showcase/library --archive dist/Zip2CAD1.0-Showcase-library-demo.zip
```

工具只复制推理所需的观测、归一化契约及指定的两个 SKP，不打包训练目标、完整训练集或第三方 SDK。每项文件都有 SHA256，输入或权重改变时拒绝继续。

```powershell
python tools/verify_release.py
python -m unittest discover -s tests -v
python tools/make_public_archive.py --output dist/Zip2CAD1.0-Showcase-source.zip
```

`outputs/` 的运行结果和本机 `.venv/` 也不进入源码包。现场每次使用新输出目录，失败会写 `run_status.json`，不会用旧结果伪装本次成功。
