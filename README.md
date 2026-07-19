# 大连海洋大学学生信息采集器

这是一个专门采集大连海洋大学官网公开信息的小工具，适合编程初学者使用。
它会从学校主页、信息公告和新闻网采集学生可能关注的新闻、通知、文件链接和
文章正文，并生成本地阅读文件。**它只会请求 `www.dlou.edu.cn` 和
`news.dlou.edu.cn`，不会跟随校外链接。**

更完整的小白说明请看：[使用说明书.md](使用说明书.md)。

## 它会做什么

- 采集学校要闻、综合新闻和信息公告。
- 读取通知或新闻的标题、发布日期、正文、原文链接和附件链接。
- 默认只记录附件链接；加 `--download-files` 才会下载附件。
- 生成 `articles.json`（完整数据）、`articles.csv`（Excel 可打开）和
  `report.md`（可直接阅读）。
- 遵守网站的 `robots.txt` 规则；每次访问之间默认等待 1 秒，请不要调得更快。

## 第一次运行（Windows）

1. 安装 Python 3.10 或更新版本。安装时勾选 **Add Python to PATH**。
2. 最简单的方式：双击项目文件夹中的 `一键启动采集器.bat`。它会采集每个栏目第 1 页、最多 10 篇文章，并在结束后提示你查看 `output` 文件夹。
3. 如果双击后提示“未找到 Python”，请先完成第 1 步并重新打开该文件。

也可以使用命令行：

1. 打开 PowerShell，进入本项目文件夹：

   ```powershell
   cd E:\codex
   ```

2. 先运行小范围采集（每个栏目 1 页、最多 10 篇文章）：

   ```powershell
   python -m dlou_crawler --pages 1 --max-articles 10
   ```

3. 在 `output` 文件夹中查看结果：

   - `report.md`：双击后可用 Markdown 阅读器打开，也可用 VS Code 预览。
   - `articles.csv`：可用 Excel 打开。
   - `articles.json`：完整、便于程序继续处理的数据。

## 常用命令

采集更完整的近期内容（每个栏目最多 3 页、最多 60 篇文章）：

```powershell
python -m dlou_crawler --pages 3 --max-articles 60
```

把公开附件也下载到 `output/files`。附件可能较大，请先确认有足够空间：

```powershell
python -m dlou_crawler --pages 1 --max-articles 20 --download-files
```

指定输出文件夹：

```powershell
python -m dlou_crawler --output D:\dlou-news
```

## 安全和使用边界

- 仅供个人学习和阅读学校公开内容；不要用于商业转载或绕过登录、验证码等限制。
- 程序不登录网站、不访问校外链接、不采集个人账户数据。
- 如果网站的 `robots.txt` 禁止抓取，程序会跳过对应页面并显示原因。
- 请保持默认 1 秒请求间隔，避免给学校网站增加负担。

## 开发与测试

项目只使用 Python 标准库，不需要安装第三方包。

```powershell
python -m unittest discover -s tests -v
```
