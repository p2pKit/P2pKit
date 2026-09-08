#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECKER="$ROOT/scripts/check-git-whitespace.sh"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p2pkit-whitespace-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# Independent byte tripwires: changing the checker and an archive together must
# not silently redefine the historical format exception.
ARCHIVE_PATHS=(
    docs/archive/evidence/v0.3/jvm-cli.log
    docs/archive/remediation/2026-06/PROBLEMS_P2PKIT.md
    docs/archive/remediation/2026-07/OPEN_DECISIONS_2026-07.md
)
ARCHIVE_SHA256=(
    7994521ea430c15f748acbbb925970d33dfbafcceab3ae1bb776dd6e1f27ec3c
    edc4723a50445bf95d927c56d39aa4ba0600cd363adaa658bddd7a06ddf0d32e
    4a7b7d8f5dcc4ba32f8410d7e78781c139e21c25f18c6ba192adb28f4fb8bff3
)

fail() {
    echo "FATAL: $*" >&2
    exit 1
}

new_repo() {
    local repo="$WORK/$1"
    mkdir -p "$repo"
    git -C "$repo" init -q
    git -C "$repo" config user.name "P2pKit Test"
    git -C "$repo" config user.email "test@p2pkit.invalid"
    git -C "$repo" config core.autocrlf false
    git -C "$repo" config core.whitespace blank-at-eol,blank-at-eof,space-before-tab
    cp "$ROOT/.gitattributes" "$repo/"
    for path in "${ARCHIVE_PATHS[@]}"; do
        mkdir -p "$(dirname "$repo/$path")"
        cp "$ROOT/$path" "$repo/$path"
    done
    printf 'clean\n' >"$repo/fixture.txt"
    git -C "$repo" add .
    git -C "$repo" commit -qm "initial"
    printf '%s\n' "$repo"
}

expect_failure() {
    local description="$1" expected_fragment="$2"
    shift 2
    if "$@" >"$WORK/check.stdout" 2>"$WORK/check.stderr"; then
        fail "$description unexpectedly passed"
    fi
    grep -Fq -- "$expected_fragment" "$WORK/check.stdout" "$WORK/check.stderr" ||
        fail "$description did not report '$expected_fragment'"
    printf 'PASS: %s\n' "$description"
}

if command -v sha256sum >/dev/null 2>&1; then
    SHA256=(sha256sum)
else
    SHA256=(shasum -a 256)
fi
for index in "${!ARCHIVE_PATHS[@]}"; do
    actual="$("${SHA256[@]}" "$ROOT/${ARCHIVE_PATHS[$index]}" | awk '{print $1}')"
    [[ "$actual" == "${ARCHIVE_SHA256[$index]}" ]] || fail "historical archive bytes changed"
    printf 'PASS: independent archive digest %s\n' "${ARCHIVE_PATHS[$index]}"
done

clean_repo="$(new_repo clean)"
(
    cd "$clean_repo"
    "$CHECKER" >/dev/null
    echo 'PASS: clean default range with historical archives'
    base="$(git rev-parse HEAD)"
    printf 'also clean\n' >>fixture.txt
    git add fixture.txt
    git commit -qm "clean change"
    "$CHECKER" "$base" "$(git rev-parse HEAD)" >/dev/null
    echo 'PASS: clean explicit range with historical archives'
    empty_tree="$(git hash-object -t tree /dev/null)"
    "$CHECKER" "$empty_tree" "$(git rev-parse HEAD)" >/dev/null
    echo 'PASS: clean all-tree fallback with historical archives'
)

committed_repo="$(new_repo committed)"
printf 'bad trailing space \n' >>"$committed_repo/fixture.txt"
git -C "$committed_repo" add fixture.txt
git -C "$committed_repo" commit -qm "bad committed whitespace"
expect_failure "committed whitespace" "trailing whitespace" \
    bash -c "cd \"$committed_repo\" && \"$CHECKER\""

all_tree_repo="$(new_repo all-tree-fallback)"
printf 'bad anywhere in head tree \n' >"$all_tree_repo/legacy.txt"
git -C "$all_tree_repo" add legacy.txt
git -C "$all_tree_repo" commit -qm "bad complete tree"
all_tree_head="$(git -C "$all_tree_repo" rev-parse HEAD)"
all_tree_base="$(git -C "$all_tree_repo" hash-object -t tree /dev/null)"
expect_failure "all-tree fallback whitespace" "trailing whitespace" \
    bash -c "cd \"$all_tree_repo\" && \"$CHECKER\" \"$all_tree_base\" \"$all_tree_head\""

staged_repo="$(new_repo staged)"
printf 'bad staged tab\t\n' >>"$staged_repo/fixture.txt"
git -C "$staged_repo" add fixture.txt
expect_failure "staged whitespace" "trailing whitespace" \
    bash -c "cd \"$staged_repo\" && \"$CHECKER\""

worktree_repo="$(new_repo worktree)"
printf 'bad worktree space \n' >>"$worktree_repo/fixture.txt"
expect_failure "worktree whitespace" "trailing whitespace" \
    bash -c "cd \"$worktree_repo\" && \"$CHECKER\""

marker_repo="$(new_repo marker)"
printf '<<<<<<< ours\nconflict\n=======\nother\n>>>>>>> theirs\n' >>"$marker_repo/fixture.txt"
git -C "$marker_repo" add fixture.txt
git -C "$marker_repo" commit -qm "committed conflict markers"
expect_failure "committed conflict markers" "leftover conflict marker" \
    bash -c "cd \"$marker_repo\" && \"$CHECKER\""

multi_repo="$(new_repo multi-commit-merge)"
multi_base="$(git -C "$multi_repo" rev-parse HEAD)"
multi_main_branch="$(git -C "$multi_repo" branch --show-current)"
git -C "$multi_repo" switch -qc topic
printf 'topic\n' >"$multi_repo/topic.txt"
git -C "$multi_repo" add topic.txt
git -C "$multi_repo" commit -qm "topic"
git -C "$multi_repo" switch -q "$multi_main_branch"
printf 'bad in earlier pushed commit \n' >"$multi_repo/earlier.txt"
git -C "$multi_repo" add earlier.txt
git -C "$multi_repo" commit -qm "earlier pushed commit"
git -C "$multi_repo" merge -q --no-ff topic -m "ending merge"
multi_head="$(git -C "$multi_repo" rev-parse HEAD)"
expect_failure "complete multi-commit merge range" "trailing whitespace" \
    bash -c "cd \"$multi_repo\" && \"$CHECKER\" \"$multi_base\" \"$multi_head\""

expect_failure "invalid commit range" \
    "base is neither an available exact commit nor the canonical empty tree" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" 0000000000000000000000000000000000000000 \"$(git -C "$clean_repo" rev-parse HEAD)\""

nonempty_tree="$(git -C "$clean_repo" rev-parse 'HEAD^{tree}')"
expect_failure "non-empty tree as base" \
    "base is neither an available exact commit nor the canonical empty tree" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" \"$nonempty_tree\" \"$(git -C "$clean_repo" rev-parse HEAD)\""

head_blob="$(git -C "$clean_repo" rev-parse 'HEAD:fixture.txt')"
expect_failure "blob as range head" "head is not an available exact commit" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" \"$(git -C "$clean_repo" rev-parse HEAD^)\" \"$head_blob\""

annotated_head_tag="$(git -C "$clean_repo" tag -a head-object -m head-object HEAD &&
    git -C "$clean_repo" rev-parse refs/tags/head-object)"
expect_failure "annotated tag object as range head" \
    "head is not an available exact commit" bash -c \
    "cd \"$clean_repo\" && \"$CHECKER\" \"$(git -C "$clean_repo" rev-parse HEAD^)\" \"$annotated_head_tag\""

# Check each representation separately. A corrupt range head must fail even
# after the index/worktree are restored; a corrupt index must fail even when
# the worktree has been restored. Clean replacement text would pass raw Git.
for index in "${!ARCHIVE_PATHS[@]}"; do
    path="${ARCHIVE_PATHS[$index]}"
    for layer in head index worktree; do
        for mutation in replace delete; do
            repo="$(new_repo "archive-$index-$layer-$mutation")"
            if [[ "$mutation" == replace ]]; then
                printf 'different but whitespace-clean historical text\n' >"$repo/$path"
                diagnostic='bytes changed in'
            else
                rm "$repo/$path"
                diagnostic='missing from'
            fi
            case "$layer" in
                head)
                    git -C "$repo" add -- "$path"
                    git -C "$repo" commit -qm 'changed archived head'
                    git -C "$repo" checkout HEAD^ -- "$path"
                    diagnostic="$diagnostic range head"
                    ;;
                index)
                    git -C "$repo" add -- "$path"
                    cp "$ROOT/$path" "$repo/$path"
                    diagnostic="$diagnostic index"
                    ;;
                worktree)
                    if [[ "$mutation" == delete ]]; then
                        diagnostic='missing or non-regular in worktree'
                    else
                        diagnostic="$diagnostic worktree"
                    fi
                    ;;
            esac
            expect_failure "archive $index $layer $mutation" "$diagnostic" \
                bash -c "cd \"$repo\" && \"$CHECKER\""
        done
    done

    neighbor="$(new_repo "neighbor-$index")"
    printf 'new unchecked whitespace \n' >"$neighbor/${path}.new"
    git -C "$neighbor" add .
    git -C "$neighbor" commit -qm 'neighboring archive'
    expect_failure "non-exempt neighboring archive $index" 'trailing whitespace' \
        bash -c "cd \"$neighbor\" && \"$CHECKER\""

    # Prove the attributes themselves do not disable conflict-marker detection
    # or the unrelated whitespace category, independently of the hash guard.
    raw="$(new_repo "raw-attributes-$index")"
    if [[ "$index" -eq 2 ]]; then
        printf 'unapproved trailing space \n' >"$raw/$path"
        diagnostic='trailing whitespace'
    else
        printf 'unapproved EOF separator\n\n' >"$raw/$path"
        diagnostic='new blank line at EOF'
    fi
    git -C "$raw" add -- "$path"
    git -C "$raw" commit -qm 'unapproved whitespace category'
    raw_empty="$(git -C "$raw" hash-object -t tree /dev/null)"
    expect_failure "non-exempt whitespace category $index" "$diagnostic" \
        git -C "$raw" diff --check "$raw_empty" HEAD -- "$path"
    printf ' \tunapproved indentation\n' >"$raw/$path"
    git -C "$raw" add -- "$path"
    git -C "$raw" commit -qm 'space before tab'
    expect_failure "archive space-before-tab $index" 'space before tab in indent' \
        git -C "$raw" diff --check "$raw_empty" HEAD -- "$path"
    printf '<<<<<<< ours\nconflict\n=======\nother\n>>>>>>> theirs\n' >"$raw/$path"
    git -C "$raw" add -- "$path"
    git -C "$raw" commit -qm 'archive conflict markers'
    expect_failure "archive conflict markers $index" 'leftover conflict marker' \
        git -C "$raw" diff --check "$raw_empty" HEAD -- "$path"
done

symlink_repo="$(new_repo symlink)"
rm "$symlink_repo/${ARCHIVE_PATHS[0]}"
ln -s "$ROOT/${ARCHIVE_PATHS[0]}" "$symlink_repo/${ARCHIVE_PATHS[0]}"
expect_failure 'archive worktree symlink' 'missing or non-regular in worktree' \
    bash -c "cd \"$symlink_repo\" && \"$CHECKER\""

crlf_repo="$(new_repo autocrlf)"
git -C "$crlf_repo" config core.autocrlf true
for path in "${ARCHIVE_PATHS[@]}"; do rm "$crlf_repo/$path"; done
git -C "$crlf_repo" checkout -- "${ARCHIVE_PATHS[@]}"
(cd "$crlf_repo" && "$CHECKER" "$(git hash-object -t tree /dev/null)" "$(git rev-parse HEAD)" >/dev/null)
echo 'PASS: exact archive bytes survive core.autocrlf=true checkout'

api_repo="$(new_repo generated-api)"
printf 'generated ABI\n\n' >"$api_repo/fixture.api"
git -C "$api_repo" add fixture.api
git -C "$api_repo" commit -qm 'generated ABI separator'
(cd "$api_repo" && "$CHECKER" >/dev/null)
echo 'PASS: existing generated ABI EOF exception remains valid'

expect_failure 'archive checker requires explicit head' 'usage:' \
    "$ROOT/scripts/check-archive-whitespace.sh"
expect_failure 'archive checker rejects tree objects' 'head is not an available exact commit' \
    bash -c "cd \"$clean_repo\" && \"$ROOT/scripts/check-archive-whitespace.sh\" \"$nonempty_tree\""

echo "RESULT: PASS — exact archive exceptions preserve range/index/worktree integrity and strict whitespace/conflict checks"
