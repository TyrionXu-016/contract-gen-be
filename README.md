# contact-gen-be

合同模版生成后端

                  ┌-------------------------------┐
                  │  浏览器 (PC / Mobile)          │
                  │  Vue3 + Vite + Axios          │
                  └------------┬------------------┘
                               │  HTTPS / WebSocket
                  ┌------------┴------------------┐
                  │  Nginx (反向代理 + 静态托管)   │
                  │  80/443 端口                  │
                  └------------┬------------------┘
                               │  uWSGI 协议
                  ┌------------┴------------------┐
                  │  Django 3.2+ (虚拟环境)       │
                  │  ┌-------------------------┐ │
                  │  │  Django REST Framework  │ │
                  │  │  JWT / Session Auth     │ │
                  │  │  CORS 已开启             │ │
                  │  └------------┬------------┘ │
                  │               │ ORM          │
                  │  ┌------------┴------------┐ │
                  │  │     Django-Sqlite3       │ │
                  │  │  (db.sqlite3 单文件)     │ │
                  │  └--------------------------┘ │
                  └-------------------------------┘

python版本：
sqlite版本：
Nginx版本：

## 后端模块

### 用户登陆

### 处理用户输入文本

### 生成合同模版

### 爬虫处理合同

### 输出文档

### 大语言模型调用
模型以及版本选择：


# 合同分块模块（contract-split-module）



## 一、 功能介绍

1\.  自动接收爬虫抓的法规数据，不用手动复制粘贴

2\.  针对「法条/合同/案例」三种文本，自动分块（拆成一小段一小段，方便向量库处理）

3\.  输出标准化数据，向量库同学可以直接用
## 二、 环境要求（必须满足）

\- Python 3.8 及以上版本

\- 推荐用 Anaconda（避免装错依赖）

## 三、 安装步骤

\### 步骤1：克隆仓库+切换到本模块分支

1\.  打开你的命令行（Windows用CMD，Mac用终端）

2\.  输入命令，克隆仓库到本地（替换成你们的仓库地址）：

&nbsp;   ```bash

&nbsp;   git clone https://github.com/小组账号/仓库名.git

&nbsp;   ```

3\.  进入仓库文件夹：

&nbsp;   ```bash

&nbsp;   cd 仓库名

&nbsp;   ```

4\.  切换到我的分块模块分支：

&nbsp;   ```bash

&nbsp;   git checkout contract-split-module

&nbsp;   ```



\### 步骤2：创建并激活Anaconda环境（关键！避免冲突）

1\.  打开 Anaconda Prompt

2\.  输入命令，创建名为 `contract\_env` 的环境（Python 3.9 版本）：

&nbsp;   ```bash

&nbsp;   conda create -n contract\_env python=3.9

&nbsp;   ```

&nbsp;   - 出现 `Proceed (\[y]/n)?` 时，输入 `y` 按回车

3\.  激活这个环境：

&nbsp;   ```bash

&nbsp;   conda activate contract\_env

&nbsp;   ```

&nbsp;   - 成功提示：命令行开头变成 `(contract\_env) C:\\...`



\### 步骤3：安装依赖库（复制命令就行）

在激活的 `contract\_env` 环境里，\*\*依次输入以下命令，每个命令按回车，等安装完成\*\*：

```bash

\# 分块模块核心依赖（必须装）

pip install langchain spacy numpy pandas

\# 爬虫模块依赖（如果要测试全流程就装）

pip install requests python-docx

\# 中文分词模型（重中之重！没有这个分不了块）

python -m spacy download zh\_core\_web\_sm

