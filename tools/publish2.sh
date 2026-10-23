#!/usr/bin/env bash
# 诗云 v3.9：推送分支、创建并合并 PR、开启 GitHub Pages（幂等）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPO="selectist377/poerty-cloud"
BRANCH="feat/v3.9-poetry-cloud"
TOKEN="${GH_TOKEN:-$(cat "$ROOT/../.ghtok")}"
API="https://api.github.com/repos/${REPO}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json" -H "User-Agent: dsh-poetry-cloud")

echo "[$(date +%H:%M:%S)] 推送 main"
git push -q "https://x-access-token:${TOKEN}@github.com/${REPO}.git" main:main
echo "[$(date +%H:%M:%S)] 推送 ${BRANCH}"
git push -q "https://x-access-token:${TOKEN}@github.com/${REPO}.git" "${BRANCH}:${BRANCH}"

echo "[$(date +%H:%M:%S)] 查找已有 PR"
NUM=$(curl -sS "${API}/pulls?head=selectist377:${BRANCH}&state=open" "${AUTH[@]}" \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j[0]["number"] if j else "")')

if [ -z "$NUM" ]; then
  echo "[$(date +%H:%M:%S)] 创建 PR"
  PR_JSON=$(python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
body = (Path(sys.argv[1]) / "docs" / "PR_BODY.md").read_text(encoding="utf-8")
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
  if [ -z "$NUM" ]; then echo "$RESP" | head -c 800; exit 1; fi
fi
echo "[$(date +%H:%M:%S)] PR #$NUM"

echo "[$(date +%H:%M:%S)] 合并 PR"
curl -sS -X PUT "${API}/pulls/${NUM}/merge" "${AUTH[@]}" \
  -d '{"merge_method":"squash"}' \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); print("merged:", j.get("merged"), "|", j.get("message"))'

echo "[$(date +%H:%M:%S)] 开启 GitHub Pages"
code=$(curl -sS -o .pages.json -w "%{http_code}" -X POST "${API}/pages" "${AUTH[@]}" \
  -d '{"source":{"branch":"main","path":"/"}}' || true)
echo "POST /pages -> $code"
head -c 400 .pages.json 2>/dev/null; echo

echo "[$(date +%H:%M:%S)] Pages 状态"
curl -sS "${API}/pages" "${AUTH[@]}" \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j.get("status"), j.get("html_url"), j.get("source"))' || true
echo "[$(date +%H:%M:%S)] 发布流程结束"
