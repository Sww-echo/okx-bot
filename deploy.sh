#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 开始 OKX Bot 自动化部署...${NC}"

# 1. 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3。请先安装 Python 3.10+"
    exit 1
fi

# 2. 创建/激活虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 创建 Python 虚拟环境 (venv)...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate
echo -e "${GREEN}✅ 已激活虚拟环境${NC}"

# 3. 安装后端依赖
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}📥 安装/更新 Python 依赖...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "⚠️ 未找到 requirements.txt，跳过依赖安装"
fi

# 4. 构建前端 (如果有 npm)
if command -v npm &> /dev/null && [ -d "frontend" ]; then
    echo -e "${YELLOW}🎨 开始构建前端页面...${NC}"
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "   安装前端依赖 (npm install)..."
        npm install
    fi
    echo "   编译静态资源 (npm run build)..."
    npm run build
    cd ..
    echo -e "${GREEN}✅ 前端构建完成${NC}"
else
    echo -e "${YELLOW}⚠️ 跳过前端构建 (未找到 npm 或 frontend 目录，将使用现有 dist 或纯API模式)${NC}"
fi

# 5. 检查配置文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚙️ 未检测到 .env 配置文件！${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ 已从模板创建 .env 文件"
    else
        touch .env
        echo "✅ 已创建空 .env 文件"
    fi
    echo -e "${YELLOW}👉 请务必编辑 .env 文件填入您的 API Key 和 Web 密码！${NC}"
    echo "   命令: nano .env"
else
    echo -e "${GREEN}✅ 配置文件 .env 已存在${NC}"
fi

# 6. 生成启动脚本
cat > start.sh << EOL
#!/bin/bash
cd "$(pwd)"
source venv/bin/activate
exec python main.py
EOL
chmod +x start.sh

echo -e "\n${GREEN}🎉 部署完成！${NC}"
echo -e "启动方式: ${GREEN}./start.sh${NC}"
echo -e "后台运行推荐: ${YELLOW}nohup ./start.sh > bot.log 2>&1 &${NC}"
