using System;
using System.Collections.Generic;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Vision.IrTracking;

public sealed record class IrBlob
{
    public PixelCoordinate Pixel { get; init; } = new();

    public double Area { get; init; }

    public double Intensity { get; init; }

    public double Confidence { get; init; } = 1d;
}

public sealed record class IrBlobFrame
{
    public required DateTimeOffset Timestamp { get; init; }

    public IReadOnlyList<IrBlob> Blobs { get; init; } = Array.Empty<IrBlob>();
}

public sealed record class ProjectedPointerSample
{
    public required PixelCoordinate ScreenPixel { get; init; }

    public required NormalizedCoordinate ScreenNormalized { get; init; }

    public required IrBlob SourceBlob { get; init; }

    public required DateTimeOffset Timestamp { get; init; }
}
