# DLOUWebsiteCrawler

大连海洋大学官网公开信息采集器

---

## 目录（根目录只有两个文件夹）

```
DLOUWebsiteCrawler/
├── 源代码/     ← 源代码（含文档与说明）
└── 发行版/     ← 已编译软件
```

| 文件夹 | 内容 |
|--------|------|
| **`源代码/`** | Python 代码、网页报告模板、打包脚本、README、LICENSE |
| **`发行版/`** | `DLOUWebsiteCrawler.exe`（双击即用） |

---

## 使用

### 发行版
双击 `../发行版/DLOUWebsiteCrawler.exe` → 开始采集 → 查看图片 / 打开报告

### 源代码
```bash
cd 源代码
python run.py
python run_cli.py --limit 8
python selfcheck.py
python build_release.py    # 打包到 ../发行版/
```

采集结果在 `源代码/output/`（本地，不上传）。

---

## 采集范围

52 栏目 · 7 分类：学校要闻 · 通知公告 · 学术科研 · 人才培养 · 教学单位 · 职能部门 · 校园文化

---

## 安全与隐私

仅访问 `dlou.edu.cn` 子域 + 官网就业网；不收集用户数据、不联网上报。

---

by:yuexuan · MIT
