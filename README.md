# 三一能源装备技服子公司 AI 项目 —— 结算材料自动归档系统

**版本：v1.0　负责人：胡家俊　更新日期：2026-11-05**

把散落在桌面、下载、邮箱附件、豆包会话里的油服结算材料，按 "项目 / 井位 → 流程节点" 自动归

一到 `~/Desktop/结算归档/`，并输出总台账与缺失材料清单。零第三方依赖，clone 下来即可跑。



***

## 一键部署（新电脑上 5 分钟跑通）

前提：macOS / Windows / Linux，装有 Python 3.9+（系统自带即可）。



```
# 1. 克隆
git clone <本仓库地址> sany-settlement-archiver
cd sany-settlement-archiver

# 2. 全自动归档（一条命令：扫描→分类→归档→台账→看板，无需中途确认）
python3 scripts/run.py auto

# 3. 打开 output/归档台账.csv 验收：状态=待确认的就是需要人工过目的

# 5. 生成总台账
python3 scripts/run.py ledger

# 6. 原件清理（归档副本校验通过后才执行）：移入废纸篓，30天后人工清空
python3 scripts/run.py trash

# v1.1 新增
python3 scripts/watch.py        # 实时监听 _收件箱，新文件自动归类
python3 scripts/dashboard.py     # 生成 Web 看板 output/dashboard.html，浏览器打开
```

后续日常使用：把新文件丢进 `~/Desktop/结算归档/_收件箱/`，然后跑一遍 `run.py all` 即可。



***

## 目录结构（归档成果）



```
~/Desktop/结算归档/
├── 00_归档总台账.xlsx / 00_缺失材料待确认.md
├── _收件箱/
├── 1_项目结算/{项目或井位}/{01_合同协议|02_工作量签认|03_核算与结算单|04_请示与用章|05_发票与挂账}/
├── 2_月度常规结算/{年月}_{类别}/
├── 3_挂账与台账/   4_框架合同与用章/   5_待确认散件/
└── 99_历史版本/   99_备份/
```

## 仓库里有什么



| 路径                    | 作用                                                    |
| --------------------- | ----------------------------------------------------- |
| `rules/keywords.json` | **全部业务规则**：时间窗口、扫描根目录、材料类型关键词、项目 / 井位词典、版本标记。加新项目只改这里 |
| `scripts/run.py`      | 一键入口：scan /plan/archive /ledger/all                   |
| `scripts/common.py`   | 时间窗口（修改 + 创建取并集）、哈希去重、docx/xlsx 正文抽取                  |
| `templates/`          | 台账模板与命名规范                                             |
| `changelog/`          | 每个版本的更新说明                                             |

## 版本纪律



* 每次有实质更新先改 `changelog/vX.Y.md` 写清 "本次更新了什么"，再提交打 tag：



```
git add -A && git commit -m "v1.1: 新增XX项目识别规则"
git tag v1.1 && git push --tags
```

## 安全红线（务必遵守）



* **本仓库只存脚本、规则、模板，不存真实结算材料**。`.gitignore` 已排除所有 pdf/xlsx/docx/zip。

* 仓库已设为 **Public**，任何人可搜索、克隆、本地部署；真实结算材料不进 git（.gitignore 已排除），金额税率等数据只存在本地 `~/Desktop/结算归档`。

* 清理策略（按负责人要求）：归档副本数量 + 大小校验通过后，原件 `run.py trash` 移入**废纸篓**，

  保留 **30 天**无异常再清空；脚本不做 `rm` 硬删，每个被移原件都记日志可回溯。