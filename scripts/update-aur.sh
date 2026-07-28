#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/update-aur.sh [options] VERSION [AUR_CHECKOUT]

Prepare the AUR package for an existing public KeydMapper release tag.

Arguments:
  VERSION       Upstream version without the "v" prefix (for example 0.2.0).
  AUR_CHECKOUT  Path to the cloned AUR repository.
                Default: ../keyd-mapper-aur relative to the main repository.

Options:
  --pkgrel N    Package release number (default: 1).
  --skip-build  Do not run makepkg --cleanbuild --syncdeps.
  --publish     Commit and push both the GitHub packaging update and AUR update.
  -h, --help    Show this help.

Without --publish, the script only prepares the changes and displays their
status for manual review.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

pkgrel=1
skip_build=false
publish=false
version=
aur_checkout=

while (($#)); do
    case "$1" in
        --pkgrel)
            (($# >= 2)) || die "--pkgrel requires a value"
            pkgrel=$2
            shift 2
            ;;
        --skip-build)
            skip_build=true
            shift
            ;;
        --publish)
            publish=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            die "unknown option: $1"
            ;;
        *)
            if [[ -z $version ]]; then
                version=$1
            elif [[ -z $aur_checkout ]]; then
                aur_checkout=$1
            else
                die "unexpected argument: $1"
            fi
            shift
            ;;
    esac
done

[[ -n $version ]] || {
    usage >&2
    exit 2
}
[[ $version =~ ^[0-9]+(\.[0-9]+)*$ ]] ||
    die "VERSION must contain dot-separated numbers, for example 0.2.0"
[[ $pkgrel =~ ^[1-9][0-9]*$ ]] ||
    die "--pkgrel must be a positive integer"

require_command git
require_command makepkg
require_command updpkgsums

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "$script_dir/.." rev-parse --show-toplevel)
packaging_dir="$repo_root/packaging/aur"

if [[ -z $aur_checkout ]]; then
    aur_checkout="$(dirname -- "$repo_root")/keyd-mapper-aur"
fi
[[ $aur_checkout = /* ]] || aur_checkout="$PWD/$aur_checkout"
[[ -d $aur_checkout ]] || die "AUR checkout does not exist: $aur_checkout"
aur_checkout=$(realpath -- "$aur_checkout")

[[ -f $packaging_dir/PKGBUILD ]] ||
    die "PKGBUILD not found in $packaging_dir"
git -C "$aur_checkout" rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    die "AUR checkout is not a Git repository: $aur_checkout"

[[ -z $(git -C "$repo_root" status --porcelain --untracked-files=normal) ]] ||
    die "the main repository has uncommitted changes"
[[ -z $(git -C "$aur_checkout" status --porcelain --untracked-files=normal) ]] ||
    die "the AUR repository has uncommitted changes"

aur_branch=$(git -C "$aur_checkout" branch --show-current)
[[ $aur_branch == master ]] ||
    die "the AUR checkout must be on its master branch (currently: $aur_branch)"

aur_origin=$(git -C "$aur_checkout" remote get-url origin 2>/dev/null || true)
[[ $aur_origin == *aur.archlinux.org/keyd-mapper.git ]] ||
    die "AUR origin does not point to the keyd-mapper AUR repository"

git -C "$aur_checkout" fetch --quiet origin master
aur_head=$(git -C "$aur_checkout" rev-parse HEAD)
aur_origin_head=$(git -C "$aur_checkout" rev-parse origin/master)
[[ $aur_head == "$aur_origin_head" ]] ||
    die "the AUR checkout is not synchronized with origin/master"

tag="v$version"
git -C "$repo_root" rev-parse --verify --quiet "refs/tags/$tag" >/dev/null ||
    die "local tag does not exist: $tag"
git -C "$repo_root" ls-remote --exit-code origin "refs/tags/$tag" >/dev/null ||
    die "tag $tag is not available on the GitHub origin"

tag_project_version=$(
    git -C "$repo_root" show "$tag:pyproject.toml" |
        awk -F'"' '/^version = "/ { print $2; exit }'
)
[[ $tag_project_version == "$version" ]] ||
    die "$tag contains project version '$tag_project_version', expected '$version'"

sed -E -i \
    -e "s/^pkgver=.*/pkgver=$version/" \
    -e "s/^pkgrel=.*/pkgrel=$pkgrel/" \
    "$packaging_dir/PKGBUILD"

(
    cd "$packaging_dir"
    updpkgsums
    makepkg --printsrcinfo >.SRCINFO
    makepkg --printsrcinfo | diff -u .SRCINFO -

    if [[ $skip_build == false ]]; then
        makepkg --cleanbuild --syncdeps
    fi
)

for file in PKGBUILD .SRCINFO .gitignore LICENSE keyd-mapper.install; do
    cp -- "$packaging_dir/$file" "$aur_checkout/$file"
done

git -C "$repo_root" diff --check
git -C "$aur_checkout" diff --check

printf '\nGitHub packaging changes:\n'
git -C "$repo_root" status --short -- packaging/aur
git -C "$repo_root" diff -- packaging/aur/PKGBUILD packaging/aur/.SRCINFO

printf '\nAUR changes:\n'
git -C "$aur_checkout" status --short
git -C "$aur_checkout" diff

if [[ $publish == false ]]; then
    printf '\nPrepared %s-%s. Review and commit both repositories manually.\n' \
        "$version" "$pkgrel"
    exit 0
fi

if [[ -n $(git -C "$repo_root" status --porcelain -- packaging/aur) ]]; then
    git -C "$repo_root" add -- packaging/aur/PKGBUILD packaging/aur/.SRCINFO
    git -C "$repo_root" commit \
        -m "packaging: update AUR package to $version-$pkgrel"
    git -C "$repo_root" push origin HEAD:main
else
    printf '\nGitHub packaging metadata is already current.\n'
fi

if [[ -n $(git -C "$aur_checkout" status --porcelain) ]]; then
    git -C "$aur_checkout" add -- \
        PKGBUILD .SRCINFO .gitignore LICENSE keyd-mapper.install
    git -C "$aur_checkout" commit -m "Update to $version-$pkgrel"
    git -C "$aur_checkout" push origin master
else
    printf 'AUR metadata is already current.\n'
fi

printf '\nPublished %s-%s to GitHub and the AUR.\n' "$version" "$pkgrel"
