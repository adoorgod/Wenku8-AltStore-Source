# 轻小说文库 Wenku8・AltStore / SideStore 源

给 iOS 上的 [轻小说文库（Wenku8）](https://github.com/mikufoxxx/Wenku8_Flutter) 客户端用的安装源。源里的安装包直接取自上游 GitHub Release，上游发版后自动跟随，不用手动找 ipa。

> 本仓库
>
> **不托管任何安装包**
>
> ，只提供版本索引（一个 JSON 文件）。所有 ipa 都来自上游仓库的 Release 资产。

## 添加源

### SideStore



1. 打开 SideStore，进入 **Sources** 页面

2. 点右上角 **+**

3. 粘贴下面的地址并确认



```
https://cdn.jsdelivr.net/gh/adoorgod/Wenku8-AltStore-Source@main/alt_store.json
```

备用地址（jsDelivr 抽风时用这个）：



```
https://raw.githubusercontent.com/adoorgod/Wenku8-AltStore-Source/main/alt_store.json
```

### AltStore（Classic / 需要 AltServer）

方法一样：**Sources → + → 粘贴地址**。之后的签名流程按 AltStore 自己的来。

添加成功后源里会出现「轻小说文库 Wenku8」，点进去按安装即可。

## 源里有什么



| 项目        | 信息                                  |
| --------- | ----------------------------------- |
| App       | 轻小说文库 Wenku8                        |
| Bundle ID | `org.mewx.wenku8Flutter`            |
| 开发者       | mikufoxxx（上游）                       |
| 最新版本      | 0.5.6（Build 2277）                   |
| 安装包大小     | 约 37.5 MB                           |
| 最低系统      | iOS 13.0                            |
| 签名状态      | **未签名**，由 SideStore / AltStore 自行签名 |

源里最多保留 8 个历史版本，旧版本可以在 App 详情页的版本列表里选。

## 更新是怎么来的



* 每 6 小时自动检查一次上游 Release（也可以手动触发，见下）

* 发现新版本就重新解析 ipa、更新源文件，源里立即能看到新版本

* 上游如果只发了 Android / 鸿蒙包而没有 iOS 包，脚本会直接退出，源保持上一次的内容，避免推一个装不上的版本

想立刻刷新：在仓库的 **Actions** 页手动运行一次「更新 AltStore / SideStore 源」，几十秒就好。

## 注意事项



* **未签名**：源只负责提供下载地址，签名和安装由 SideStore / AltStore 完成

* **小组件**：ipa 里带小组件扩展 `ReadingWidgets`。SideStore 签名时会一起签，但小组件要正常显示通常需要 App Groups 权限；如果签名报错，可以只签主应用

* **免费**：上游应用完全免费，任何收费的 "付费版 / 激活码" 都是骗人的

* **非官方**：本项目和源都不是轻小说文库官方产物

* **版权**：小说、封面、插图归各自权利人所有，请只阅读你有权访问的内容

## 常见问题

**源加进去后图标是空白或默认图**

图标走的是 `raw.githubusercontent.com`，国内网络偶尔会加载失败。不影响安装，换个网络后在 SideStore 里下拉刷新源即可。

**源里显示的还是旧版本**

给缓存留点时间：raw 地址有几分钟 CDN 缓存，jsDelivr 的 `@main` 缓存可能更久。急的话去 Actions 手动跑一次，或者直接把地址里的 `@main` 换成最新的 commit 哈希。

**安装时报签名失败**

多半是小组件的 App Group 权限问题。可以先只签主应用，或者换 SideStore 的签名方式重试。如果提示证书过期，需要在 SideStore 里重新登录 Apple ID 刷新证书。

**添加源提示无法读取**

先确认仓库是 Public 状态，再把地址换成 raw 那个备用地址试试；也可以直接在浏览器打开源地址，能返回一段 JSON 就说明源本身没问题。

**安装后打不开 / 闪退**

确认系统版本在 iOS 13 以上，并且签名时没有只签了部分架构。仍不行的话去上游仓库提 issue，附上版本号和设备信息。

## 关于本仓库

源文件由 GitHub Actions 从上游 Release 自动生成，不需要人工维护，也不接受安装包上传。



* 上游应用：[mikufoxxx/Wenku8\_Flutter](https://github.com/mikufoxxx/Wenku8_Flutter)

* 源文件：`alt_store.json`

* 生成脚本：`scripts/update_source.py`

* 定时任务：`.github/workflows/update-source.yml`