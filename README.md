# 每日家常菜公众号自动发布系统

每天自动从网上抓取家常菜做法、配料和图片，并发布到微信公众号。

## 快速开始

### 1. 克隆仓库

```bash
git clone <your-repo-url> && cd wechat-recipe-publisher
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的微信公众号凭证
```

必须配置的环境变量：

| 变量 | 说明 |
|---|---|
| `WECHAT_APP_ID` | 微信公众号 AppID |
| `WECHAT_APP_SECRET` | 微信公众号 AppSecret |
| `PRIMARY_SCRAPER` | 首选爬虫源（默认 `douguo`） |
| `RECIPE_CATEGORY` | 食谱分类（默认 `家常菜`） |

### 4. 本地测试

```bash
python src/main.py
```

### 5. 配置 GitHub Actions（自动定时运行）

1. 将代码推送到 GitHub 仓库
2. 在仓库 `Settings > Secrets and variables > Actions` 中添加：
   - `WECHAT_APP_ID`
   - `WECHAT_APP_SECRET`
3. 在微信公众平台后台 `开发 > 基本配置 > IP 白名单` 中添加 GitHub Actions Runner IP
4. GitHub Actions 会每天北京时间 08:45 自动运行

也可以手动触发：`Actions > 每日家常菜自动发布 > Run workflow`

## 工作原理

```
定时触发 (08:45 BJT)
  → 从豆果美食/美食天下/下厨房抓取随机食谱
  → 下载图片 → 上传微信公众号 CDN
  → 构建精美图文 HTML
  → 创建草稿 → 提交发布
```

## 项目结构

```
wechat-recipe-publisher/
├── .github/workflows/
│   └── daily-publish.yml      # GitHub Actions 定时任务
├── src/
│   ├── main.py                # 主入口
│   ├── config.py              # 配置管理
│   ├── scrapers/              # 爬虫层
│   │   ├── base.py            # Recipe 数据模型 + 基类
│   │   ├── douguo.py          # 豆果美食（首选，实测稳定）
│   │   ├── meishichina.py     # 美食天下（备选）
│   │   └── xiachufang.py      # 下厨房（有反爬限制）
│   ├── wechat/                # 微信公众号 API
│   │   ├── client.py          # Token/草稿/发布
│   │   ├── image.py           # 图片下载+上传
│   │   └── article.py         # HTML 模板构建
│   └── utils/                 # 工具
│       ├── logger.py          # 日志
│       └── retry.py           # 重试装饰器
├── requirements.txt
├── .env.example
└── README.md
```

## 爬虫源说明

| 源 | 状态 | 说明 |
|---|---|---|
| **豆果美食** (douguo.com) | ✅ 可用 | 首选源，实测稳定 |
| **美食天下** (meishichina.com) | ⚠️ 备选 | 可用，链接较少 |
| **下厨房** (xiachufang.com) | ❌ 受限 | 有人机验证，自动回退 |

爬虫失败时自动按优先级回退到下一个源，保证每天都有内容发布。

## 文章样式

每篇发布的文章包含：
- 🖼️ 封面大图
- 📝 食谱摘要
- 📋 食材清单（表格形式）
- 🍳 详细步骤（编号卡片 + 步骤图）
- 💡 烹饪小贴士
- 🔗 来源标注

## 依赖

- Python 3.8+
- requests + BeautifulSoup4（爬虫）
- Pillow（图片处理）
- python-dotenv（本地开发环境变量）

## License

MIT
