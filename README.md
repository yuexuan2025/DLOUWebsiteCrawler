# DLOUWebsiteCrawler

大连海洋大学（DLOU）官网公开信息采集器。支持 GUI / 命令行，导出 JSON、CSV 与本地网页报告。

> 仅采集学校官网公开栏目，不收集用户数据、不联网上报。

---

## 本地目录（本机磁盘）

```
DLOUWebsiteCrawler/
├── 源代码/              ← 可上传的源码全在这里
│   ├── dlou_crawler/    ← 核心包（采集 / 解析 / 报告 / GUI）
│   ├── run.py           ← GUI 入口
│   ├── run_cli.py       ← 命令行入口
│   ├── selfcheck.py
│   ├── build_release.py / build.spec
│   ├── index.html / app.css / app.js
│   └── README.md / LICENSE / requirements.txt / .gitignore
├── 发行版/
│   └── DLOUWebsiteCrawler.exe   ← 只放这一个
└── .venv-build/         ← 本机打包环境（不要上传）
```

| 路径 | 上传 | 说明 |
|------|------|------|
| `源代码/` 里面全部文件 | ✅ | 全选后粘贴到 GitHub，作为源代码 |
| `发行版/` 里 EXE | ✅ | 粘贴到 GitHub（可再建 `发行版/` 文件夹） |
| `.venv-build/` | ❌ | 打包临时环境，绝不能上传 |
| `output/`（运行产生） | ❌ | 采集结果，不公开 |

---

## 上传 GitHub（鼠标操作即可）

1. 打开 **`源代码`** 文件夹 → 全选 → 复制到 GitHub 上传  
2. 打开 **`发行版`** → 复制 `DLOUWebsiteCrawler.exe` → 再上传（可放进 `发行版/` 文件夹）

上传后 GitHub 仓库根目录就是源代码，和「把 `源代码/` 里的文件贴上去」一致。

---

## 使用

### 发行版
双击 `发行版/DLOUWebsiteCrawler.exe` → 开始采集 → 打开报告。

### 源码（在 `源代码/` 目录下）

```text
python run.py
python run_cli.py --limit 8
python selfcheck.py
python build_release.py
```

采集结果统一写在 **`源代码/output/`**（源码运行时 GUI 与命令行相同；也可用 `--out` 改目录）。  
发行版 EXE 会把结果写在 **`发行版/output/`**（EXE 旁）。

`build_release.py` 会把 EXE 写到上一级的 `发行版/DLOUWebsiteCrawler.exe`（与本机布局一致）。

可选依赖（图片预览）：`pip install -r requirements.txt`

---

## 采集范围

52 栏目 · 7 分类：学校要闻 · 通知公告 · 学术科研 · 人才培养 · 教学单位 · 职能部门 · 校园文化

默认仅访问 `dlou.edu.cn` 子域 + 官网就业信息网。

**说明：**
- 主站 `www.dlou.edu.cn`、教务处等部分页面需 **统一身份认证** 或 **校内网**。校外采集时程序会保留标题/链接，并在正文中注明「正文未抓取」。
- 输出目录：`源代码/output/`（JSON / CSV / 网页报告）。

---

## 安全与隐私

- 仅请求校园公开页面，主机白名单（用真实 hostname，防 userinfo 绕过）
- 重定向也限制在校内域；报告 HTML 经白名单净化
- 不收集用户数据、不上传采集结果
- 图片预览仅下载白名单主机，且重定向同受限制

---

## License

[MIT](LICENSE) · by yuexuan
