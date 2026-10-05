# Validate E01 access on Windows/WSL

Run on a Windows machine. Docker on the development Mac does not validate WSL.
Ubuntu 24.04 is a candidate environment; its dependency combination has not yet
been validated by this project. Keep failure reports as well as successful ones.

## Install and identify WSL

In Administrator PowerShell, if a suitable distribution is not already installed:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart if requested and create the Linux user account. Confirm WSL version 2:

```powershell
wsl --list --verbose
wsl --version
```

Reference: [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install).

## Clone and install dependencies

Inside Ubuntu, install the tools, then clone the remote URL supplied for this repo:

```bash
sudo apt update
sudo apt install git python3 ewf-tools sleuthkit
git clone git@github.com:datenwerft/vscode_forensic_framework.git
cd vscode_forensic_framework/docs
```

For a private remote, authenticate Git on Windows/WSL first. Do not put tokens in
the repository URL or commit them. No Docker, BMad, or Python packages are required
for these two probes.

## Run against Linux-local storage

```bash
python3 _verification/e01-access/probe.py \
  _verification/e01-access/runs/wsl-local --extended
python3 _verification/e01-access/probe.py \
  _verification/e01-access/runs/wsl-macos-reference --extended \
  --source _verification/e01-access/fixtures/macos-fat16
```

The first command creates a synthetic image; the second reads the exact committed
Mac reference. Each output directory must be new. Both should print `passed`.
The checks cover reading, verification, missing/truncated segments, cancellation,
and unchanged segment content. They do not prove write prevention.

Record the environment:

```bash
uname -a > _verification/e01-access/runs/wsl-environment.txt
cat /etc/os-release >> _verification/e01-access/runs/wsl-environment.txt
dpkg-query -W ewf-tools sleuthkit libewf2 >> _verification/e01-access/runs/wsl-environment.txt
```

## Read evidence stored on Windows

Copy only `fixtures/macos-fat16` to a Windows directory such as
`C:\forensic-proof\macos-fat16`. From WSL, read it with:

```bash
python3 _verification/e01-access/probe.py \
  _verification/e01-access/runs/wsl-windows-source --extended \
  --source /mnt/c/forensic-proof/macos-fat16
```

This deliberately tests the Windows-to-WSL filesystem boundary while keeping run
outputs in Linux storage. See [Microsoft filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).

## Return results

Return the three generated `report.json` files, `wsl-environment.txt`, and the
PowerShell WSL version output. `runs/` is ignored deliberately; do not force-add
the generated images. Selected reports can be reviewed and copied into `results/`
afterward. The committed fixture manifest supplies the expected source, logical
image, and file hashes for comparison.

The larger platform gate still includes ext4, native WSL write prevention,
Windows-source reconnection, and editor integration. These instructions cover the
initial reproducible access check only.
