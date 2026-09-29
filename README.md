# DLOUWebsiteCrawler

大连海洋大学（DLOU）官网公开信息采集器。支持图形界面与命令行，一键采集公开栏目，导出 JSON、CSV 和本地网页报告。

> 仅采集学校官网公开栏目，不收集用户数据、不联网上报。

## 功能

- 覆盖 **52 个栏目 · 7 个分类**：学校要闻 · 通知公告 · 学术科研 · 人才培养 · 教学单位 · 职能部门 · 校园文化
- GUI / CLI 双入口，可调并发与每栏篇数
- 结果导出：`articles.json`、`articles.csv`、可搜索筛选的网页报告
- 主机白名单与 HTML 净化，报告可本地直接打开

## 快速开始

### 方式一：直接使用（推荐）

1. 下载 [发行版/DLOUWebsiteCrawler.exe](发行版/DLOUWebsiteCrawler.exe)（Windows）
2. 双击运行 → 点击「开始采集」→「打开报告」

采集结果写在 EXE 旁的 `output/` 目录。

### 方式二：从源码运行

需要 Python 3.10+（标准库即可；图片预览可选安装 Pillow）。

```bash
# 图形界面
python run.py

# 命令行
python run_cli.py --limit 8 --workers 12

# 自检
python selfcheck.py
```

采集结果默认写在当前目录下的 `output/`，也可用 `--out` 指定目录。

可选依赖：

```bash
pip install -r requirements.txt
```

## 项目结构

```text
├── dlou_crawler/          # 核心包（采集 / 解析 / 报告 / GUI）
├── run.py                 # GUI 入口
├── run_cli.py             # 命令行入口
├── selfcheck.py           # 自检脚本
├── index.html / app.css / app.js   # 网页报告模板
├── build_release.py       # 打包发行版 EXE
└── 发行版/                 # 编译好的 Windows 程序
```

打包本地 EXE（Windows）：

```bash
python build_release.py
```

## 采集说明

- 默认仅访问 `dlou.edu.cn` 子域及官网就业信息网
- 主站、教务处等部分页面需**统一身份认证**或**校内网**。校外采集时会保留标题与链接，并在正文中注明「正文未抓取」
- 输出包含 JSON / CSV / 网页报告（`output/index.html`）

## 安全与隐私

- 仅请求校园公开页面，主机白名单（使用真实 hostname，防止 userinfo 绕过）
- 重定向限制在允许域内；报告 HTML 经白名单净化
- 不收集用户数据、不上传采集结果
- 图片预览仅下载白名单主机，且重定向同受限制

## License

[MIT](LICENSE) · by yuexuan
