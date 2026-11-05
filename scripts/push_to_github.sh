#!/bin/bash
# 一键发布到 GitHub（Private 仓库）—— 首次推送用
# 用法：
#   GH_USER=你的GitHub用户名 GH_TOKEN=你的PersonalAccessToken bash scripts/push_to_github.sh
# 推送内容：main 分支全部提交 + v1.0 标签；更新说明见 commit message 与 changelog/
set -e
: "${GH_USER:?请先提供 GitHub 用户名：GH_USER=xxx}
: "${GH_TOKEN:?请先提供 Personal Access Token（repo 权限）：GH_TOKEN=xxx}"
REPO="sany-energy-tech-service-ai"

echo "[1/3] 创建 Private 仓库：$REPO"
curl -fsS -u "$GH_USER:$GH_TOKEN" https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO\",\"private\":true,
      \"description\":\"三一能源装备技服子公司AI项目 - 结算材料自动归档系统（负责人：胡家俊）\"}" \
  >/dev/null 2>&1 && echo "  已创建" || echo "  仓库已存在，继续"

echo "[2/3] 关联远程并推送 main + 全部标签"
git remote remove origin 2>/dev/null || true
git remote add origin "https://$GH_USER:$GH_TOKEN@github.com/$GH_USER/$REPO.git"
git push -u origin main --tags

echo "[3/3] 完成"
echo "仓库地址：https://github.com/$GH_USER/$REPO"
echo "提醒：token 只用于本次推送，已在 remote 配置中出现；如需清除密码，运行 git remote set-url origin https://github.com/$GH_USER/$REPO.git"
