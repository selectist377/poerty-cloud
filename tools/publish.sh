#!/usr/bin/env bash
# 诗云 v3.9 交付：初始化 main、推送特性分支、创建并合并 PR、开启 GitHub Pages
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO="selectist377/poerty-cloud"
BRANCH="feat/v3.9-poetry-cloud"
TOKEN="${GH_TOKEN:-$(cat "$ROOT/../.ghtok")}"
API="https://api.github.com/repos/${REPO}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json" -H "User-Agent: dsh-poetry-cloud")

echo "==> 检查工作区"
git status --short | head -20

echo "==> 建立 main 初始提交（仅仓库骨架）"
git checkout -q -B main
git add .gitignore .nojekyll
git -c user.name="dsh-mobile" -c user.email="local@dsh" commit -q -m "chore: 初始化仓库骨架" || echo "（main 已有提交）"

echo "==> 建立特性分支并提交全部交付物"
git checkout -q -B "$BRANCH"
git add -A
git -c user.name="dsh-mobile" -c user.email="local@dsh" commit -q -m "feat: 诗云 v3.9 全量交付（协议校订 + 100 首诗 + 盲测 + 静态站点）" || echo "（无新增改动）"

echo "==> 推送 main"
git push -q "https://x-access-token:${TOKEN}@github.com/${REPO}.git" main:main

echo "==> 推送特性分支"
git push -q "https://x-access-token:${TOKEN}@github.com/${REPO}.git" "${BRANCH}:${BRANCH}"

echo "==> 创建 PR"
PR_JSON=$(python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
body = (root / "docs" / "PR_BODY.md").read_text(encoding="utf-8")
print(json.dumps({
    "title": "诗云 v3.9：协议校订、100 首终稿、五代理盲测与静态站点",
    "head": "feat/v3.9-poetry-cloud",
    "base": "main",
    "body": body,
}, ensure_ascii=False))
PY
)
RESP=$(curl -sS -X POST "${API}/pulls" "${AUTH[@]}" -d "$PR_JSON")
NUM=$(printf '%s' "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("number",""))')
if [ -z "$NUM" ]; then echo "$RESP" | head -c 600; exit 1; fi
echo "PR #$NUM 已创建"

echo "==> 合并 PR（squash）"
curl -sS -X PUT "${API}/pulls/${NUM}/merge" "${AUTH[@]}" \
  -d '{"merge_method":"squash","commit_title":"诗云 v3.9：协议校订、100 首终稿、五代理盲测与静态站点 (#'"$NUM"')"}' \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); print("merged:", j.get("merged"), "|", j.get("message"))'

echo "==> 开启 GitHub Pages（main 分支根目录）"
code=$(curl -sS -o .pages.json -w "%{http_code}" -X POST "${API}/pages" "${AUTH[@]}" \
  -d '{"source":{"branch":"main","path":"/"}}' || true)
echo "POST /pages -> $code"
cat .pages.json 2>/dev/null | head -c 400; echo

echo "==> 查询 Pages 状态"
curl -sS "${API}/pages" "${AUTH[@]}" | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j.get("status"), j.get("html_url"), j.get("source"))' || true

echo "==> 完成"
