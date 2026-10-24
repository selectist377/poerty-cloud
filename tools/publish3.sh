#!/usr/bin/env bash
# 后续小修：推送 feat 分支、创建并合并 PR #2
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPO="selectist377/poerty-cloud"
BRANCH="feat/v3.9-poetry-cloud"
TOKEN="${GH_TOKEN:-$(cat "$ROOT/../.ghtok2")}"
API="https://api.github.com/repos/${REPO}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json" -H "User-Agent: dsh-poetry-cloud")

echo "[$(date +%H:%M:%S)] 推送 ${BRANCH}"
GIT_TERMINAL_PROMPT=0 git -c http.version=HTTP/1.1 push \
  "https://x-access-token:${TOKEN}@github.com/${REPO}.git" \
  "${BRANCH}:${BRANCH}" --force || { echo "push failed"; exit 1; }

NUM=$(curl -sS "${API}/pulls?head=selectist377:${BRANCH}&state=open" "${AUTH[@]}" \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); print(j[0]["number"] if j else "")')
if [ -z "$NUM" ]; then
  BODY='## 变更\n\n- 统一「傍晚」用字，修正异体字「晩」。\n- 新增 `.github/workflows/validate.yml`：在 push/PR 时校验 100 首诗稿形式、复现评分与生成物，并用 `git diff --exit-code` 确认报告/诗集/网页与仓库一致。\n- 本地已通过：`validate_poems.py` 0 失败；重跑生成链后 `git diff` 为空。'
  JSON=$(python3 -c 'import json,sys; print(json.dumps({"title":"fix: 统一用字并加入 CI 校验","head":"feat/v3.9-poetry-cloud","base":"main","body":sys.argv[1]}))' "$BODY")
  NUM=$(curl -sS -X POST "${API}/pulls" "${AUTH[@]}" -d "$JSON" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("number",""))')
fi
[ -z "$NUM" ] && { echo "PR 创建失败"; exit 1; }
echo "[$(date +%H:%M:%S)] PR #$NUM"
curl -sS -X PUT "${API}/pulls/${NUM}/merge" "${AUTH[@]}" -d '{"merge_method":"squash"}' \
  | python3 -c 'import json,sys; j=json.load(sys.stdin); print("merged:", j.get("merged"), "|", j.get("message"))'
echo "[$(date +%H:%M:%S)] 完成"
