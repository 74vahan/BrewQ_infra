#!/usr/bin/env bash
# Правило №5 (VibeCode): в коде не должно быть случайной кириллицы.
#
# Кириллица допустима в документации (*.md), в комментариях и в файле
# переводов app/web/src/i18n/locales/ru.json. Везде остальное — ошибка:
# опечатка вроде кириллической «с» вместо латинской «c» компилируется, но
# ломается в рантайме.
#
# Подход: для каждого файла по расширению выбирается язык, из исходника
# вырезаются комментарии (и docstring'и в .py) с сохранением нумерации строк,
# строковые литералы остаются на месте. Любая кириллица в остатке — ошибка.
# Это строже «только смешанные токены»: русский текст в строке или
# идентификаторе тоже считается ошибкой.
#
# Отдельно (только предупреждение, код выхода не меняется) ищутся «смешанные»
# токены латиница+кириллица во ВСЕХ текстовых файлах, включая комментарии и
# документацию: именно так выглядит опечатка с похожей буквой в русском слове.
#
# Запуск из любого места: ci/check-cyrillic.sh [корень_репозитория]
set -uo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT" || exit 2

# (*UTF) включает UTF-режим PCRE: без него grep не принимает диапазон.
CYRILLIC='(*UTF)[\x{0400}-\x{052F}]'
MIXED='(*UTF)(*UCP)\b(?=[\p{L}\p{N}_]*[A-Za-z])(?=[\p{L}\p{N}_]*[\x{0400}-\x{052F}])[\p{L}\p{N}_]+'

# Файлы, где кириллица разрешена целиком.
# Second entry (BrewQ_image only, exact path from the repo root): the barista
# stub page in terraform/scripts/bootstrap.sh.tftpl has one deliberate Russian
# line, the ru localization next to the en/hy lines.
ALLOWED_PATHS='(^|/)app/web/src/i18n/locales/ru\.json$|^terraform/scripts/bootstrap\.sh\.tftpl$'
# Пути, которые не проверяются вообще.
SKIPPED_PATHS='(^|/)(node_modules|dist|build|\.venv|venv|\.git|\.claude|\.ruff_cache|\.pytest_cache|_image)/'

# Вырезает комментарии, сохраняя число строк.
#   lc  — маркер строчного комментария ("" если нет)
#   bs/be — начало/конец блочного комментария ("" если нет)
#   triple=1 — строки в тройных кавычках считать docstring'ами (Python)
#   ws=1 — строчный комментарий начинается только после пробела (shell/yaml/ini)
strip_comments() {
  awk -v lc="$1" -v bs="$2" -v be="$3" -v triple="${4:-0}" -v ws="${5:-0}" '
    BEGIN { inblock = 0; intriple = ""; instr = "" }
    {
      line = $0; out = ""; n = length(line); i = 1
      while (i <= n) {
        c = substr(line, i, 1)
        if (intriple != "") {
          if (substr(line, i, 3) == intriple) { intriple = ""; i += 3 } else { i++ }
          continue
        }
        if (inblock) {
          if (be != "" && substr(line, i, length(be)) == be) { inblock = 0; i += length(be) } else { i++ }
          continue
        }
        if (instr != "") {
          out = out c
          if (c == "\\" && i < n) { out = out substr(line, i + 1, 1); i += 2; continue }
          if (c == instr) instr = ""
          i++
          continue
        }
        if (triple && (substr(line, i, 3) == "\"\"\"" || substr(line, i, 3) == "\x27\x27\x27")) {
          intriple = substr(line, i, 3); i += 3; continue
        }
        if (bs != "" && substr(line, i, length(bs)) == bs) { inblock = 1; i += length(bs); continue }
        if (lc != "" && substr(line, i, length(lc)) == lc) {
          prev = (i == 1) ? " " : substr(line, i - 1, 1)
          if (!ws || prev == " " || prev == "\t") break
        }
        if (c == "\"" || c == "\x27" || (c == "`" && lc == "//")) { instr = c }
        out = out c
        i++
      }
      # Обычные кавычки не переносятся на следующую строку (кроме шаблонных).
      if (instr != "`") instr = ""
      print out
    }'
}

# Sets KIND by file name: py | hash | slash | html | sql | none | skip
set_kind() {
  case "$1" in
    *.py|*.pyi) KIND=py ;;
    *.mako|*.sh|*.bash|*.yml|*.yaml|*.toml|*.ini|*.cfg|*.txt|*.tf) KIND="hash" ;;
    *.example|*.dockerignore|Dockerfile|*/Dockerfile|*.Dockerfile) KIND="hash" ;;
    .gitignore|*/.gitignore|.gitattributes|*/.gitattributes) KIND="hash" ;;
    *.js|*.mjs|*.cjs|*.ts|*.tsx|*.jsx|*.css|*.scss) KIND=slash ;;
    *.html|*.htm|*.svg|*.xml) KIND=html ;;
    *.sql) KIND=sql ;;
    *.json|*.tftpl|*.conf) KIND=none ;;
    *) KIND=skip ;;
  esac
}

list_files() {
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # --others --exclude-standard: a repository without commits is checked too
    # (plain `git ls-files` would be empty and the check would pass vacuously).
    git ls-files --cached --others --exclude-standard
  else
    find . -type f -not -path './.git/*' | sed 's#^\./##'
  fi | sort -u
}

files=()
scan=()     # files for the mixed-token warning (everything textual)
while IFS= read -r file; do
  [ -f "$file" ] || continue
  [[ "$file" =~ $SKIPPED_PATHS ]] && continue
  set_kind "$file"
  case "$file" in *.md) scan+=("$file"); continue ;; esac
  [ "$KIND" = skip ] && continue
  scan+=("$file")
  files+=("$file")
done < <(list_files)

failed=0
warned=0

# Warning only: Latin and Cyrillic letters inside ONE word, in all text files
# including comments, docs and ru.json - this is what a look-alike typo is.
if [ "${#scan[@]}" -gt 0 ]; then
  mixed_hits="$(LC_ALL=C grep -nP "$MIXED" -- "${scan[@]}" 2>/dev/null | head -50 || true)"
  if [ -n "$mixed_hits" ]; then
    warned="$(printf '%s
' "$mixed_hits" | wc -l)"
    echo "WARNING: words mixing Latin and Cyrillic letters (possible look-alike typo):"
    printf '%s
' "$mixed_hits" | sed 's/^/    /'
  fi
fi

checked=0
for file in "${files[@]:-}"; do
  [[ "$file" =~ $ALLOWED_PATHS ]] && continue
  set_kind "$file"
  checked=$((checked + 1))

  case "$KIND" in
    py)    stripped="$(strip_comments '#' '' '' 1 0 <"$file")" ;;
    hash)  stripped="$(strip_comments '#' '' '' 0 1 <"$file")" ;;
    slash) stripped="$(strip_comments '//' '/*' '*/' 0 0 <"$file")" ;;
    html)  stripped="$(strip_comments '' '<!--' '-->' 0 0 <"$file")" ;;
    sql)   stripped="$(strip_comments '--' '/*' '*/' 0 0 <"$file")" ;;
    *)     stripped="$(cat -- "$file")" ;;
  esac

  hits="$(printf '%s
' "$stripped" | LC_ALL=C grep -nP "$CYRILLIC" || true)"
  if [ -n "$hits" ]; then
    echo "ERROR: Cyrillic outside comments: $file"
    printf '%s
' "$hits" | sed 's/^/    /'
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
      echo "::error file=${file}::Cyrillic outside comments (VibeCode rule 5)"
    fi
    failed=1
  fi
done

if [ "$failed" -eq 0 ]; then
  echo "OK: no stray Cyrillic in code (files checked: ${checked}, mixed-word warnings: ${warned})"
fi

exit "$failed"
