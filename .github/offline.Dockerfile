# 离线镜像：证明"运行期零网络"（`plan/02` §4.3）
#
# 用法（CI 的 offline job）：
#   docker build -f .github/offline.Dockerfile -t errcode-atlas-offline .
#   docker run --rm --network none errcode-atlas-offline python tools/check_sprint_layout.py
#
# 三条纪律：
#   1. **镜像里不要 pip install** —— 运行期零依赖，判定路径只用标准库；
#      这样"无网络容器里跑通"顺带证明了"零第三方依赖"。
#   2. **必须给 PYTHONPATH** —— 本仓是 src 布局，`COPY . /work` 之后默认 sys.path 上没有
#      `src/`，否则连 `--version` 都会报 `No module named errcode_atlas`。
#   3. 编码钉住 —— 门的输出是中文，容器默认 C locale 会编不了。

FROM python:3.12-slim

WORKDIR /work
COPY . /work

ENV PYTHONPATH=/work/src \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1

# 冒烟：镜像自己就能跑起来（构建期不联网判定路径，只跑一个 --version）
RUN python -m errcode_atlas --version

CMD ["python", "-m", "errcode_atlas", "--help"]