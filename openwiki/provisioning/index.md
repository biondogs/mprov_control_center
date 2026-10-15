---
type: Documentation Index
title: "Provisioning"
description: "Files and subdirectories in Provisioning."
---

# Files

- [Job Queue and Jobservers](job-queue.md) - How mProv Control Center delegates work to jobservers: Job/JobModule/JobServer/JobStatus models, signal-driven job creation from model saves, the pull-based claiming protocol, heartbeat garbage collection, artifact dependency injection, and the UI status-change feed.
- [PXE Boot and Provisioning Flow](pxe-boot-flow.md) - End-to-end bare-metal provisioning in mProv Control Center: the no-auth /ipxe/ endpoint, jobserver artifact redirects, busybox initrd boot scripts, stateless vs stateful installs with GRUB/EFI handling, NADS self-registration, and IPMI power control.
