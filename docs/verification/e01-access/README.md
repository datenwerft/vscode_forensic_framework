# E01 access experiment

Status: macOS and Debian 12 ARM64 container proofs passed. The native macOS
[write-boundary experiment](MACOS-READONLY.md) also passed. The tested Debian 13
combination failed. WSL remains untested; milestone 1 is not complete.

This disposable experiment evaluates direct libewf-backed Sleuth Kit readers using
synthetic evidence. It does not implement the evidence engine or VS Code extension.
It creates no evidence filesystem mounts and does not decide the production stack.

## Recorded results

Nine passing runs, one retained failed run, and six successful comparisons are in
[results/comparison.json](../../../_verification/e01-access/results/comparison.json). Other `results/*.json` files
retain command outputs, versions, timings, and segment hashes. Generated images
and working copies stay under ignored `runs/`.

| Environment | Reader versions | Observed result |
|---|---|---|
| macOS 26.6.2 ARM64 | Sleuth Kit 4.15.0; ewf tools 20140816 | MBR/FAT16 and partitionless ext4 passed |
| Debian 12 ARM64, Docker Desktop Linux VM | Sleuth Kit 4.11.1+dfsg-1+b1; ewf-tools/libewf2 20140813-1+b1; libbfio1 20170123-6 | MBR/FAT16 and partitionless ext4 passed |
| Debian 13 ARM64, Docker Desktop Linux VM | Sleuth Kit 4.12.1+dfsg-3; ewf-tools/libewf2 20140816-1+b1; libbfio1 20170123-6+b2 | Partition reader terminated with SIGSEGV (-11) |
| Windows through WSL | Not run | Requires Windows/WSL validation |

Debian 13 failed with both a first-segment argument and an explicit segment list,
including the image generated on macOS. Standalone `ewfinfo` and `ewfverify`
succeeded. The precise faulty library has not been isolated. The first failed run
is retained in `results/linux-01.json`; this is not a claim that all Linux builds fail.

The successful Docker image ID was
`sha256:f8e3d570fa9006d336dde8c7f789e6c64259e5a4d2351a11a473b059ce15005f`.
The Dockerfile pins its base-image digest, but apt repositories remain mutable.
Captured package versions identify the tested build. This older package combination
is an experimental comparison, not a production distribution recommendation.

## Checks that passed

- Opened a ten-segment E01 set from E01 alone, inspected metadata, discovered the
  FAT16 partition, listed files, and read their exact expected bytes.
- Read a 3 MiB allocated file across segments with matching hashes on both hosts.
- Created ext4 with Linux `mke2fs`, acquired it as partitionless segmented E01, and
  read the same file contents on Linux and macOS.
- Read the exact macOS-generated segments on Linux and Linux-generated segments
  on macOS; compared segment hashes, logical-disk hashes, and file hashes.
- Explicit verification matched the expected logical image SHA-256. Missing middle,
  missing final, and truncated middle segments produced nonzero error exits.
- Cancelled and reaped an active `icat` reader after receiving its first bytes.
  Output-pipe backpressure prevents early completion. This tests active-process
  cancellation, not interruption during a blocked storage read or a mount operation.
- Original segment content hashes remained unchanged in every successful run.
- In a separate non-root container, disposable mode-0666 evidence files were mounted
  read-only. Opening evidence for writing and creating a file both failed with
  `EROFS`, while the extended read test passed. That container had no writable
  evidence alias, Docker socket, network, or Linux capabilities.

The original macOS access tests use mode-0444 sources and before/after hashes.
The subsequent [native boundary test](MACOS-READONLY.md) uses writable disposable
files and verifies that a restricted worker cannot mutate them. That experimental
launcher is not yet a production packaging decision. The Linux bind-mount check
proves that specific container boundary only, not protection against host software.

Generic missing-segment diagnostics need a product-level resolver with actionable
errors. Executable presence and advertised format support are insufficient capability
checks: the Debian 13 crash demonstrates why real access probes and process isolation
are needed.

## Reproduction

Requires Python 3, `ewfacquirestream`, `ewfinfo`, `ewfverify`, `mmls`, `fls`, and
`icat`; Sleuth Kit must include EWF support. Run without Python `-O` because the
experiment uses assertions. Use these scripts only with their synthetic fixtures.
Probe output directories must not exist. `compare.py` refreshes the shareable reports.

From the repository root, on a fresh run:

```sh
python3 _verification/e01-access/probe.py _verification/e01-access/runs/macos-01
python3 _verification/e01-access/probe.py _verification/e01-access/runs/macos-extended --extended
docker build -t forensic-e01-proof:bookworm _verification/e01-access
docker run --rm --network none --cap-drop ALL \
  --security-opt no-new-privileges --read-only --tmpfs /tmp --user 1000:1000 \
  --mount "type=bind,source=$PWD/_verification/e01-access,target=/probe,readonly" \
  --mount "type=bind,source=$PWD/_verification/e01-access/runs,target=/work" \
  forensic-e01-proof:bookworm python3 /probe/linux_suite.py
```

The Linux suite runs baseline and extended FAT16 checks, reads the macOS evidence,
and generates/tests ext4. Cross-read its images on macOS:

```sh
python3 _verification/e01-access/probe.py _verification/e01-access/runs/macos-linux-evidence \
  --extended --source _verification/e01-access/runs/linux-suite/extended
python3 _verification/e01-access/probe.py _verification/e01-access/runs/macos-ext4 \
  --extended --source _verification/e01-access/runs/linux-suite/ext4 \
  --raw _verification/e01-access/runs/linux-suite/ext4.raw
```

For the write-boundary check, copy generated extended FAT16 segments to
`runs/readonly-source`, set those copies to mode 0666, and create an empty
`runs/readonly-result`. Run `readonly_probe.py` in the Bookworm container with only
`probe.py` and `readonly_probe.py` mounted beneath `/probe`, the source directory
at `/evidence:ro`, and the result directory at `/results:rw`. Use the same non-root,
no-capabilities restrictions. Do not also expose `runs/` writable in this container.

To reproduce the failed Debian 13 baseline, build with
`--build-arg BASE_IMAGE=debian:stable-slim@sha256:ee12ffb55625b99d62837a72f037d9b2f18fd0c787a89c2b9a4f09666c48776c`
and run the default probe into `/work/linux-01`. Package versions can change on rebuild.

After all recorded runs exist, `python3 _verification/e01-access/compare.py` verifies
passing results, the retained failure, unchanged hashes, and six cross-run comparisons.

## Remaining milestone work

1. Actual WSL run, including Windows source/path visibility and integration.
2. Independently acquired images, additional filesystems/EWF variants, encrypted and
   layered volumes, large directories, and large-image performance. The 9 MiB FAT16
   and 32 MiB ext4 fixtures are functional checks, not benchmarks.
3. Production-supported macOS write-prevention packaging, extending the successful
   native experiment; WSL write-attempt tests; journal and recovery checks for any
   future mount-backed provider.
4. Permission-denied inputs, byte corruption beyond truncation, interrupted sessions,
   storage-I/O cancellation, and resource recovery. Mounted-resource cleanup was not
   tested because this access route created no evidence filesystem mounts.
5. Distribution/licensing review of exact shipped dependencies and engine protocol
   design, including bounded reads/listings, provenance, and process isolation.

Keep direct readers as a candidate alongside other safe facilities detected on each
host. These results do not impose FAT/ext-only or Sleuth Kit-only product support.
The original product paper is unchanged.

## Primary references

- [libewf project](https://github.com/libyal/libewf): container support and tool roles.
- [mmls manual](https://www.sleuthkit.org/sleuthkit/man/mmls.html): partition listing.
- [icat manual](https://www.sleuthkit.org/sleuthkit/man/icat.html): content reads.

Captured local command results establish installed-build behavior; upstream support
claims alone do not establish tested capabilities.

Historical JSON transcripts retain the absolute paths used when the probes ran,
before the repository layout was corrected. New runs use the root-level paths above.
