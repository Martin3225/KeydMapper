# Releasing KeydMapper

## 1. Choose the version

Use the same version in:

- `pyproject.toml` → `project.version`
- `packaging/aur/PKGBUILD` → `pkgver`

For a new upstream release, reset `pkgrel` in `PKGBUILD` to `1`, then refresh
the AUR metadata:

```bash
cd packaging/aur
makepkg --printsrcinfo > .SRCINFO
cd ../..
```

The first prepared release is already set to `0.1.0`.

## 2. Verify the release

```bash
python -m pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest -q KeydMapper/tests
python -m build
desktop-file-validate data/keyd-mapper.desktop
cd packaging/aur
makepkg --printsrcinfo | diff -u .SRCINFO -
cd ../..
```

Review the changes and ensure the working tree is clean:

```bash
git diff --check
git status
```

## 3. Publish on GitHub

Commit the release, push it, and wait for GitHub Actions to pass:

```bash
git add --all
git commit -m "release: v0.1.0"
git push origin main
```

Create an annotated tag on the tested commit and push it:

```bash
git tag -a v0.1.0 -m "KeydMapper 0.1.0"
git push origin v0.1.0
```

Create the GitHub release from that tag, either in the GitHub web interface or
with GitHub CLI:

```bash
gh release create v0.1.0 --title "KeydMapper 0.1.0" --generate-notes
```

GitHub automatically attaches source archives. No generated wheel is required
for the AUR package because its `PKGBUILD` builds directly from the tagged
source.

## 4. Publish on the AUR

Register an AUR account and add an SSH public key first. Check that the
`keyd-mapper` package name is still available, then clone its AUR repository:

```bash
cd ..
git clone ssh://aur@aur.archlinux.org/keyd-mapper.git keyd-mapper-aur
```

Copy the prepared files from the KeydMapper checkout:

```bash
cp KeydMapper/packaging/aur/PKGBUILD keyd-mapper-aur/
cp KeydMapper/packaging/aur/.SRCINFO keyd-mapper-aur/
cp KeydMapper/packaging/aur/.gitignore keyd-mapper-aur/
cp KeydMapper/packaging/aur/LICENSE keyd-mapper-aur/
cp KeydMapper/packaging/aur/keyd-mapper.install keyd-mapper-aur/
cd keyd-mapper-aur
```

Build and install the package locally before publishing it:

```bash
makepkg --cleanbuild --syncdeps --install
```

If the build succeeds, publish the AUR metadata:

```bash
git add PKGBUILD .SRCINFO .gitignore LICENSE keyd-mapper.install
git commit -m "Initial import: 0.1.0-1"
git push
```

The AUR repository contains only the packaging metadata, its ignore rules and
0BSD license, and the install notice. Application development continues in the
GitHub repository.

## Updating an existing AUR package

- New KeydMapper version: update `pkgver`, reset `pkgrel=1`, and regenerate
  `.SRCINFO`.
- Packaging-only fix: keep `pkgver`, increment `pkgrel`, and regenerate
  `.SRCINFO`.
- Always create and push the corresponding GitHub tag before publishing the AUR
  update, because the AUR build reads that tag.
- After the tag is public, regenerate the source checksum with `makepkg -g` or
  `updpkgsums`, update `b2sums`, and regenerate `.SRCINFO`.
