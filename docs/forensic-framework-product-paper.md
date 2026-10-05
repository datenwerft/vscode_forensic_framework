# Forensic Evidence Workspace for VS Code

Product concept · Working draft · 4 October 2026

## Product vision

Build a forensic framework extension for Visual Studio Code that lets investigators add evidence, open it read-only, and explore its contents from a single workspace. The first product capability is reliable evidence access: opening forensic images, physical disks, volumes, ZIP archives, and CSV datasets while preserving the relationship between each item and its original source.

E01 is the priority forensic image format. Linux, macOS, and Windows through WSL are target environments from the beginning. The product should use the filesystem capabilities available in the environment running the evidence engine rather than limit investigators to a fixed list of filesystems.

This paper records the agreed product direction and proposes an initial scope. Implementation libraries, packaging, licensing, and the exact supported environment matrix remain to be validated.

## The problem

Before analysis can begin, an investigator must make evidence accessible. Different sources require different tools and workflows: segmented forensic images must be resolved, disk partitions exposed, filesystems opened, archives browsed, and structured datasets interpreted.

These preparation steps can become disconnected from the investigation itself. Source locations, mount options, verification results, and working copies may be tracked separately, making it harder to understand how a file or finding relates to the evidence.

The extension should make evidence access a visible, repeatable part of the case. Investigators should know what they opened, how it was opened, what the environment can read, and whether integrity verification has actually occurred.

## Intended users and first use case

The initial audience is investigators and incident responders who want to work with evidence alongside scripts, notes, and analysis tools in VS Code.

The primary first-release use case is an investigator opening a segmented E01 image, discovering its partitions, and browsing files from any filesystem that the active environment can safely expose read-only.

The product is initially an evidence-access foundation. Timelines, analysis orchestration, and reporting can build on that foundation in later releases.

## Product principles

- **Protect original evidence.** Reads must not modify source content. Indexes, caches, extracted files, and analysis results belong in separate case storage.
- **Use available capabilities.** Discover the readers, drivers, and mount facilities available to the active engine and explain what is missing when access is unavailable.
- **Keep provenance visible.** Every exposed item must retain a reference to its evidence source and its location within that source.
- **Separate access from verification.** Opening evidence successfully does not establish its integrity.
- **Make platform differences understandable.** Offer a consistent workflow while reporting environment-specific limitations honestly.
- **Fail clearly.** Missing segments, unsupported formats, encryption, corruption, and permission failures must produce actionable explanations.

## Core experience

The main action is **Add evidence**. The investigator selects a source, reviews its detected type and location, and adds it to a case. The extension registers the source and opens it using an appropriate provider.

The Evidence Explorer presents each source according to its structure:

| Source | Explorer representation | Access approach |
|---|---|---|
| E01 image | Evidence → disk or volume → partitions, where present → directories and files | Read E01 container, expose disk data, then use available filesystem support |
| Physical disk | Evidence → device → partitions → directories and files | Read-only device access where the environment permits it |
| Volume | Evidence → volume → directories and files | Read-only access to an accessible volume |
| ZIP archive | Evidence → archive → directories and files | Archive reader; explicit extraction into case storage when needed |
| CSV dataset | Evidence → table → columns and rows | Table reader with explicit parsing settings |

“Mount” is an operation used for sources that need filesystem exposure. ZIP and CSV sources share the same entry point and evidence lifecycle without requiring an operating-system mount.

### Evidence lifecycle

1. **Select:** choose an image, device, volume, archive, or dataset.
2. **Detect:** identify the source type and check the required access capabilities.
3. **Register:** assign an evidence ID and record its source location, size where available, and supplied acquisition details.
4. **Open:** establish read-only access and expose the source structure.
5. **Explore:** browse directories, preview supported content, or view a table.
6. **Verify:** run an explicit verification operation when supported and record its scope and result.
7. **Close:** release readers and mounts owned by the extension without removing the case record.

Evidence remains registered if opening fails or its source becomes unavailable. The investigator can inspect the error and retry or reconnect it.

## E01 as the first priority

The first implementation must support a complete E01 browsing workflow, not merely recognize the extension or display container metadata.

It must resolve segmented image sets, identify missing or unreadable segments, read available image metadata, expose the contained disk or volume data, discover partitions where present, and open supported filesystems read-only.

E01 container access and filesystem access are separate responsibilities. For example, libewf’s `ewfmount` exposes the raw storage data contained in an EWF image; further partition and filesystem handling is required for ordinary disk-image file browsing. This makes libewf a candidate dependency, subject to technical and licensing review. [Source: libewf project](https://github.com/libyal/libewf)

The first release should not impose an NTFS-only product restriction. It should advertise the capabilities detected in the active environment. Explicitly tested filesystem and environment combinations should be documented separately from other detected capabilities.

## Cross-platform approach

The proposed architecture separates the VS Code interface from a local evidence engine:

```text
VS Code extension
  Case management · Evidence Explorer · Viewers · Progress
                         │
                  Common evidence API
                         │
                    Evidence engine
                  Linux · macOS · WSL
                         │
       E01 · Device/volume · ZIP · CSV providers
                         │
        Available readers and filesystem facilities
```

On Linux and macOS, the engine runs locally. On Windows, the proposed initial execution environment is WSL. Source paths and device access must be interpreted from the engine’s environment, and the UI must clearly identify which environment is active.

The product must not assume that a device visible to Windows is also accessible inside WSL, or that a filesystem supported on one host is available on another. A capability check should determine whether the full access path is usable: source visibility, container reader, volume handling, filesystem support, permissions, and enforceable read-only access.

The extension should expose evidence through a consistent virtual explorer. The engine may use controlled operating-system mounts internally when needed. Exposing a mount path for external tools can be added as an explicit capability.

## Evidence engine and providers

Each provider should offer a common lifecycle: detect a source, inspect metadata, open it, list or query its contents, read content, report capabilities, and close resources. Optional operations include verification and extraction.

Providers must preserve source-specific behavior. A CSV reader exposes rows and columns; a filesystem reader exposes directories and byte streams. The common model should unify provenance and lifecycle without pretending every source is a filesystem.

The engine should handle long-running work outside the editor interface, provide progress where measurable, support cancellation, and record meaningful failures. If elevated access is required, it should be limited to the specific device or mount operation rather than running the entire editor with elevated privileges.

## Case data and provenance

The case record should include:

- Stable case and evidence identifiers.
- Evidence type, original location, segment set where applicable, and investigator-supplied source notes.
- Registration time, available acquisition metadata, and the distinction between supplied and observed information.
- Reader and engine versions, relevant access settings, and opening or closing outcomes.
- Verification records, including algorithm, scope, expected value if supplied, computed value where applicable, result, and time.
- References from browsed or extracted items to their parent evidence and internal location.

Working data belongs in a separate case directory. References should use evidence IDs and internal locations rather than depend solely on temporary mount paths. Reconnecting a moved source must be explicit; matching filenames alone must not establish identity.

These records support traceability. They do not by themselves establish a complete organizational chain-of-custody process.

## Read-only access and verification

Read-only behavior is a release requirement. Disabling edit commands in the UI is insufficient: the underlying access path must prevent writes to evidence. Mount behavior must account for filesystem-specific write activity, including recovery or journal replay where applicable. If a safe access path cannot be established, the product must explain the limitation instead of opening the source writable.

For a physical disk or an already-mounted volume, the extension can control its own access but cannot assume that other software is prevented from writing. The UI should distinguish the extension’s access mode from broader source write protection.

Verification should remain separate from evidence availability. Suggested states are **Not verified**, **In progress**, **Passed for the stated scope**, **Failed**, **Cancelled**, and **Unavailable**. A computed hash with no comparison value should be reported as a recorded hash, not as proof that the source matches an acquisition original.

Large sources must not require a complete verification pass before basic browsing unless an investigator explicitly chooses that behavior. A result must identify whether it concerns container checks, logical image data, source files, or another defined scope.

## First release scope

The first release should deliver:

- Case creation and persistent evidence registration.
- E01 and segmented E01 opening, metadata inspection, partition discovery, and file browsing through available read-only filesystem support.
- Linux, macOS, and Windows-through-WSL installation and capability checks.
- Evidence details, clear access errors, progress, cancellation, and resource cleanup.
- Explicit verification with recorded scope and results where supported.
- Reopening a case and reconnecting unavailable evidence.

Physical disks, volumes, ZIP, and CSV are part of the product direction. Their providers should follow the E01 milestone, using the same case records and lifecycle.

The initial release excludes deleted-file recovery, carving, memory analysis, automated interpretation of evidence, cross-source timelines, collaborative case editing, and final forensic report generation. Ordinary filesystem browsing does not imply access to deleted entries, unallocated space, or all forensic metadata.

## Delivery milestones

| Milestone | Result | Completion evidence |
|---|---|---|
| 1. Cross-platform access proof | Open a segmented E01 and browse a contained filesystem on Linux, macOS, and WSL | Demonstrated workflow on all target environments; documented dependencies and read-only behavior |
| 2. Usable evidence workspace | Create a case, register evidence, browse files, close, and reopen | Persistent provenance and useful handling of unavailable sources |
| 3. Verification and resilience | Verify supported sources, cancel operations, and handle failures | Recorded verification scope; tests for missing segments, damaged input, denied access, and interrupted operations |
| 4. Additional sources | Add device/volume, ZIP, and CSV providers | Consistent registration and provenance with appropriate source-specific views |

## Acceptance criteria

The E01 milestone is complete when an investigator can select the first segment of a valid test image, have the full set resolved, inspect metadata, discover its volumes, browse a filesystem supported by the active environment, read a file, and close the evidence cleanly.

Validation must also demonstrate that:

- Missing segments and unsupported access capabilities yield specific errors.
- Evidence source content remains unchanged during opening, browsing, verification, and closing.
- The engine enforces read-only access; before-and-after source checks support that validation.
- Verification status never implies a check that did not run.
- Cancellation and ordinary failures release resources created by the extension.
- Recovery after an interrupted session identifies stale resources without disturbing unrelated mounts.
- Opening the same reference evidence across tested environments yields consistent file content, with differences in exposed metadata documented.
- Large directory listings and long operations do not block the editor interface.

## Principal uncertainties

The first technical proof should resolve dependency distribution and licensing, mount facilities and privileges on each platform, WSL source and device visibility, filesystem-specific read-only behavior, and practical performance for large segmented images.

Additional design decisions include how the engine communicates with the extension, how native dependencies are installed and updated, which EWF variants are initially supported, and how encrypted or layered volumes are identified and reported. These should be settled through targeted prototypes before claiming broad compatibility.

## Success measures

Early evaluation should measure successful E01 opening across the tested environment matrix, time to first directory listing, browsing responsiveness on large images, clarity of failure messages, clean closure of resources, and investigator effort required to reconnect and resume a case.

The first product promise is concrete: **bring E01 evidence into a VS Code investigation workspace, browse what the active environment can safely read, and retain a clear record of the source and access process.**
