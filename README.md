# Z-Library：Mac 本地运行

## 使用
1. 编辑 `keywords.txt`，每行一个关键词，然后保存。
2. 双击桌面的「启动 Z-Library.command」。
3. 已接入你提供的登录 Cookie，会自动读取。本机凭证位置：`/Users/jingtianyu/Library/Application Support/ZLibrary/cookies.txt`（仅当前用户可读写）。若该文件不存在，才提示输入邮箱和密码。
4. CSV 保存在项目目录，书籍文件保存在 `downloads/`。再次运行时，已有 CSV 保留，新文件带时间戳。

程序保留原脚本的自动下载设置。只搜索时，在项目目录运行：

```sh
./.venv/bin/python zlibrary_search.py --search-only
```

本地检查：

```sh
./.venv/bin/python zlibrary_search.py --check
./.venv/bin/python test_local.py zlibrary_search.py
```

## 环境和验证
- 独立 Python 3.12 虚拟环境，不修改系统 Python。
- 依赖固定为 zlibrary 1.0.2；完整安装版本见 requirements.lock.txt。
- 本地测试使用模拟搜索结果和本机 HTTP 测试文件，不代表真实账号登录、在线搜索或书籍下载已成功。
- 上游接口说明：https://github.com/sertraline/zlibrary
- 桌面原脚本保持不变。修改副本、差异和验证记录见 evidence/VERIFICATION.txt。
- 回退脚本接收待恢复的副本路径，先保留当前副本，再恢复导入原版；不会删除下载文件。

## 本次联网结果
登录验证请求收到 HTTP 503；尚未确认 Cookie 有效，也未执行真实书籍下载。本地测试通过不等于线上服务可用。稍后可运行 `./.venv/bin/python zlibrary_search.py --check-login` 重试。
