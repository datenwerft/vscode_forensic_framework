# Native macOS read-only boundary experiment

Result: passed on macOS 26.6.2 ARM64 using the installed Sleuth Kit 4.15.0 and
libewf tools reporting version 20140816. The recorded result is
[results/macos-boundary.json](../../../_verification/e01-access/results/macos-boundary.json).

## Boundary tested

An unsandboxed, trusted parent creates disposable evidence copies and canary files.
It launches a worker using [macos-readonly.sb](../../../_verification/e01-access/macos-readonly.sb), which denies all
file-write operations and network operations. The worker and its reader children
return results through stdout/stderr pipes; only the parent writes result files.
No evidence filesystem mount is created, and no writable file descriptors are
passed into the worker. Stdin is a read-only `/dev/null` descriptor opened by the
parent. Other descriptors are closed on launch.

This tests a native operating-system boundary beyond ordinary Unix mode bits:
the disposable source files and canaries have mode 0666, and their owner runs the
worker. The parent first confirms it can open the evidence read-write without
modifying it. A separate unsandboxed control executes the same mutation tests.

## Observations

All 12 control operations succeeded. All 12 corresponding protected operations
failed with `EPERM` (errno 1):

| Operation | Control | Protected worker |
|---|---|---|
| Overwrite existing bytes | Allowed | Denied |
| Append bytes | Allowed | Denied |
| Truncate a file | Allowed | Denied |
| Create a file | Allowed | Denied |
| Rename a file | Allowed | Denied |
| Unlink a file | Allowed | Denied |
| Change permissions | Allowed | Denied |
| Change timestamps | Allowed | Denied |
| Write through a pre-existing symlink | Allowed | Denied |
| Write through a pre-existing hard link | Allowed | Denied |
| Open for writing relative to a directory descriptor | Allowed | Denied |
| Write from a child process | Allowed | Denied |

The protected worker also failed to open the actual disposable E01 source for
writing, for both fixture sets. Under the same profile it successfully:

- Inspected E01 metadata and discovered the FAT16 partition.
- Listed files from segmented FAT16 and partitionless ext4 images.
- Read `HELLO.TXT` and the 3 MiB `SPAN.BIN`, matching reference content and hashes.
- Verified each logical image against the existing reference SHA-256.
- Cancelled and reaped active large-file readers with SIGTERM (-15).

Hashes, sizes, permission modes, and modification timestamps of the evidence and
protected canaries matched before and after. Access times and extended attributes
were not measured. The cancellation check uses output-pipe backpressure and does
not demonstrate cancellation during a blocked storage operation.

## Reproduce

The existing generated fixtures `runs/macos-extended` and `runs/linux-suite/ext4`
must exist. The script accepts only an output-directory argument for normal use;
fixture inputs are the previous experiment's generated files.

```sh
python3 _verification/e01-access/macos_readonly.py \
  _verification/e01-access/runs/macos-boundary-new
```

Run from the repository root and use a new output directory. Run from a normal macOS terminal, not from an existing
sandbox that prohibits applying a nested profile. No root privileges are required.
The completed run was `macos-boundary-04`; preceding runs preserve development
failures: an unavailable Python xattr API, denied nested sandbox creation, and
Python attempting to open `/dev/null` read-write. The final harness uses timestamp
checks and inherits a read-only stdin; it does not weaken the write-denial profile.

## Design implications and limits

The experiment supports separating a read-only evidence worker from a trusted
case-storage writer. The worker should fail closed if its boundary cannot be
applied; a real product must not silently launch it unrestricted. The parent must
not pass writable evidence descriptors or implement arbitrary file-write requests
on the worker's behalf.

This profile uses `allow default` with file-write and network denials. It is an
experiment in direct filesystem write prevention, **not** a complete containment
policy for malicious code. IPC-mediated operations, service delegation, inherited
writable-descriptor attacks, devices, mount helpers, and kernel vulnerabilities
were not tested. Other host processes can still modify the evidence.

Do not select this exact launcher as the production security contract yet. Apple
Developer Technical Support explains that custom SBPL profiles are undocumented
for third-party use and that `sandbox-exec` is deprecated; App Sandbox entitlements
are the supported application mechanism. See the
[Apple discussion](https://developer.apple.com/forums/thread/661939).
This support status is separate from the behavior demonstrated on this Mac.

Before release, validate a supported signed-helper/App Sandbox design or another
maintained isolation approach against this mutation suite, test fail-closed launch
and IPC restrictions, and run it across the supported macOS versions. Physical
devices and mount-backed filesystem access require separate proofs.

The next platform gap remains actual Windows/WSL validation. The product paper and
its release requirements have not been weakened by this experiment.
