# 轻小说文库 Wenku8 · AltStore / SideStore 源

上游项目 [`mikufoxxx/Wenku8_Flutter`](https://github.com/mikufoxxx/Wenku8_Flutter) 只提供未签名 ipa，没有官方 AltStore 源。这个仓库用 GitHub Actions **定时读取上游最新 Release**，自动重新生成 `alt_store.json`，所以 SideStore 每次刷新源都能拿到新版本。

## 仓库结构

```
.
├── .github/workflows/update-source.yml   # 定时任务：每 6 小时生成一次源
├── scripts/update_source.py              # 生成脚本（读 Release → 解析 ipa → 写 JSON）
├── alt_store.json                        # 源文件（由脚本生成，不要手改）
├── icon.png                              # 从 ipa 里提取的 App 图标（由脚本生成）
└── README.md
```

## 部署步骤

1. 在 GitHub 新建一个 **Public** 仓库（必须公开，否则 SideStore 拿不到源文件），默认分支保持 `main`。
2. 把本目录的所有文件推到该仓库（注意 `.github/workflows/` 也要一起上传，否则 Actions 不会出现）。
3. 打开仓库的 **Actions** 页，左侧选中「更新 AltStore / SideStore 源」，点 **Run workflow** 手动跑一次。
   - 跑完后 `alt_store.json` 里的 `iconURL` 会被自动写成你这个仓库的真实地址，`icon.png` 也会就位。
   - 确认这次运行是绿色勾；若失败，点进去看日志。
4. 等 Actions 提交完成后，你的源地址就是：

   ```
   https://raw.githubusercontent.com/<你的用户名>/<你的仓库名>/main/alt_store.json
   ```

   也可以换成 jsDelivr 加速地址（AltStore 官方推荐，返回的 Content-Type 更标准）：

   ```
   https://cdn.jsdelivr.net/gh/<你的用户名>/<你的仓库名>@main/alt_store.json
   ```

5. 在 **SideStore → Sources → +** 里粘贴上面的地址即可。

## 自动更新是怎么生效的

- `update-source.yml` 每 6 小时（以及你手动触发时）运行一次。
- 脚本调 GitHub API 取上游最新 Release（默认跳过 prerelease），找到以 `-ios-unsigned.ipa` 结尾的资产。
- 下载该 ipa，解析 `Payload/Runner.app/Info.plist`，拿到 `CFBundleIdentifier`、版本号、Build、最低系统版本、隐私权限说明，并提取 `AppIcon60x60@2x.png`。
- 重写 `alt_store.json`，把新版本插到 `versions` 列表最前面，同时保留历史版本（最多 8 个）。
- 有变化就自动 commit + push；没变化就跳过。
- SideStore 每次下拉刷新源时重新拉取这个 JSON，于是就能看到并安装新版本。

> SideStore 自身的「自动更新 App」是另一套机制（需要在 SideStore 里开启后台刷新），源文件只负责把新版本**暴露**出来。

## 常用自定义

改 `.github/workflows/update-source.yml` 里的环境变量即可：

| 变量 | 作用 | 默认 |
|---|---|---|
| `REPO_OWNER` / `REPO_NAME` | 要跟踪的上游仓库 | `mikufoxxx` / `Wenku8_Flutter` |
| `IPA_ASSET_SUFFIX` | iOS 包文件名后缀 | `-ios-unsigned.ipa` |
| `MAX_VERSIONS` | 源里保留的历史版本数 | `8` |
| `INCLUDE_PRERELEASE` | 是否把 prerelease 当成可用版本 | `0` |
| `SOURCE_BRANCH` | 源文件所在分支（影响 iconURL） | `main` |

如果想跟踪别的项目，改 `REPO_OWNER`、`REPO_NAME`、`IPA_ASSET_SUFFIX` 三个即可。

本地手动跑一次：

```bash
python scripts/update_source.py
```

## 注意事项

- **安装包未签名**：Source 只负责提供下载地址，签名仍由 SideStore 完成。
- **小组件扩展**：ipa 内包含 `Payload/Runner.app/PlugIns/ReadingWidgets.appex`（`org.mewx.wenku8Flutter.ReadingWidgets`）。SideStore 签名时会一并签扩展；小组件要正常显示，通常需要 App Groups 权限，签名时注意别把扩展漏掉或权限给错。
- **API 限额**：Actions 里用的是仓库自带的 `GITHUB_TOKEN`，每小时 1000 次请求，完全够用；本地无 token 时是每小时 60 次，手动跑一次也没问题。
- **缓存**：`raw.githubusercontent.com` 有几分钟 CDN 缓存；jsDelivr 的 `@main` 缓存可能更久，如果刚发版看不到更新，等一会儿或换个版本号引用。
- 本仓库不托管任何应用安装包，`downloadURL` 全部指向上游 GitHub Release 的原始资产。
