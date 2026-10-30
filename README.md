# 抓蚂 · 节目单专用仓库

本仓库只保存公开频道数据、EPG 生成脚本和定时发布流程，不包含抓蚂应用源码。

频道来自 iptv-org，节目单使用固定版本 iptv-org/epg，每天北京时间 06:00、18:00 自动生成，支持手动运行。Pages Source 为 GitHub Actions，工作流使用官方部署动作发布校验通过的产物；gh-pages 分支保存上一份成功数据。生成失败时保留原线上数据。

[节目单 XMLTV](https://ivan-whatkuku.github.io/zhuama-epg/epg/guide.xml) · [覆盖及有效期](https://ivan-whatkuku.github.io/zhuama-epg/epg/manifest.json)

上游线路可用性与节目单覆盖因频道而异；不提供历史视频回看。
