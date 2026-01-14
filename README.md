# Refurboard

![A smart phone with two blue and orange people leaping out of the screen. Below is the text Refurboard.](assets/logo.png)

[![Homepage Azure Deployment](https://github.com/kevinl95/Refurboard/actions/workflows/azure-static-web-apps-ashy-pebble-0a0fa1710.yml/badge.svg)](https://github.com/kevinl95/Refurboard/actions/workflows/azure-static-web-apps-ashy-pebble-0a0fa1710.yml)
[![Automated Tests](https://github.com/kevinl95/Refurboard/actions/workflows/test.yml/badge.svg)](https://github.com/kevinl95/Refurboard/actions/workflows/test.yml)

## Overview

Refurboard is entering a full .NET 8 + Avalonia rewrite that modernizes the original LED-pen whiteboard concept. The refreshed stack prioritizes:

- **OpenCvSharp IR Tracking** (currently in flight) with USB or phone webcam ingestion.
- **Versioned JSON Settings** that auto-heal, migrate, and align with locale-specific installer SKUs.
- **Automation Hooks** covering device detection, calibration prompts, and plugin-based OS integrations.
- **Per-Locale Bundles** so every installer ships shared binaries plus language packs.

Python-era services (Flask server, Kivy UI, cx_Freeze builds, pytest suites) have been removed from this repository. Historical details remain in Git history and the MkDocs wiki for reference.

Visit the [Azure-hosted homepage and Wiki](https://refurboard.com) for roadmap milestones and long-form documentation.

## Current Capabilities

- **Avalonia Desktop Shell** with a bootstrap dashboard surfacing config validity, locale, and calibration needs.
- **Schema-Backed Configuration** stored in `%APPDATA%/Refurboard` (Windows), `~/Library/Application Support/Refurboard` (macOS), or `~/.config/Refurboard` (Linux).
- **CI Pipelines** for .NET restore/build/test plus locale-specific SKU artifacts.
- **MkDocs Wiki** (in `refurboard-wiki/`) deployed via Azure Static Web Apps.

Upcoming milestones will add camera enumeration, FoV overlays, IR calibration workflows, automation plug-ins, and localization-aware UX.

## Getting Started

### Prerequisites

- .NET SDK 8.0 or later (`dotnet --list-sdks` to confirm)
- Desktop OS supported by Avalonia (Windows, macOS, or Linux)

### Clone & Restore

```bash
git clone https://github.com/kevinl95/Refurboard.git
cd Refurboard
dotnet restore Refurboard.sln
```

### Build & Run

```bash
# Build the entire solution
dotnet build Refurboard.sln

# Launch the Avalonia desktop app
dotnet run --project src/Refurboard.App/Refurboard.App.csproj
```

On first launch the bootstrapper writes `refurboard.config.json` into your platform app-data directory, validates it against the embedded schema, and highlights whether calibration should auto-start and which locale bundle is active.

### Testing

```bash
dotnet test Refurboard.sln --configuration Release
```

CI mirrors these commands (see `.github/workflows/test.yml`) and additionally assembles locale-specific installer archives.

## Configuration Model

The schema lives at `src/Refurboard.Core/Configuration/config.schema.json` and is embedded into the core library. Important sections:

- `metadata`: schema/app versioning, locale, timestamp data.
- `camera`: device identifiers, resolution, FoV, exposure, and intensity thresholds.
- `calibration`: screen bounds, normalized corner points, calibration timestamps, and device fingerprints.

`ConfigurationBootstrapper` creates or repairs the JSON file and exposes a `ConfigBootstrapResult` consumed by the Avalonia UI. Future automation features (calibration triggers, plugin hints, locale self-repair) build on this surface.

## Solution Layout

```
Refurboard.sln
├── src/
│   ├── Refurboard.App/        # Avalonia desktop application
│   └── Refurboard.Core/       # Config + upcoming camera/IR/business logic
├── refurboard-wiki/           # MkDocs content for https://refurboard.com
└── .github/workflows/         # CI for .NET + documentation deployments
```

## Contributing

1. Fork the repo and branch off `main`.
2. Run `dotnet build` and `dotnet test` before submitting PRs.
3. Keep schema changes synchronized with installer scripts and documentation.
4. Coordinate on issues for camera/vision, localization, and plugin contracts.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
