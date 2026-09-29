# DLOUWebsiteCrawler

大连海洋大学（DLOU）官网公开信息采集器。支持图形界面与命令行，一键采集公开栏目，导出 JSON、CSV 和本地网页报告。

> 仅采集学校官网公开栏目，不收集用户数据、不联网上报。

## 功能

- 覆盖 **52 个栏目 · 7 个分类**：学校要闻 · 通知公告 · 学术科研 · 人才培养 · 教学单位 · 职能部门 · 校园文化
- GUI / CLI 双入口，可调并发与每栏篇数
- 结果导出：`articles.json`、`articles.csv`、可搜索筛选的网页报告
- 主机白名单与 HTML 净化，报告可本地直接打开

## 快速开始

### 直接使用（Windows）

到本仓库 **[Releases](../../releases)** 页面下载 `DLOUWebsiteCrawler.exe`，双击运行 → 「开始采集」→「打开报告」。

采集结果保存在程序旁边的 `output/` 文件夹。

### 从源码运行

需要 Python 3.10+（核心功能仅用标准库；GUI 图片预览可选安装 Pillow）。

```bash
# 图形界面
python run.py

# 命令行
python run_cli.py --limit 8 --workers 12

# 自检
python selfcheck.py
```

采集结果默认写在 `output/`，也可用 `--out` 自定义目录。

可选依赖：

```bash
pip install -r requirements.txt
```

## 项目结构

```text
├── dlou_crawler/     # 核心包（采集 / 解析 / 报告 / GUI）
├── run.py            # 图形界面入口
├── run_cli.py        # 命令行入口
├── selfcheck.py      # 自检脚本
├── index.html        # 网页报告模板
├── app.css / app.js  # 报告样式与交互
└── build_release.py  # 打包 Windows 程序
```

本地打包 Windows 程序：

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
