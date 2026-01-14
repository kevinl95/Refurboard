using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Threading;
using System.Threading.Tasks;
using Refurboard.Core.Configuration.Models;
using Refurboard.Core.Vision.SpatialMapping;

namespace Refurboard.Core.Vision.IrTracking;

public interface IIrBlobSelector
{
    IrBlob? Select(IReadOnlyList<IrBlob> blobs);
}

public sealed class LargestBlobSelector : IIrBlobSelector
{
    public static LargestBlobSelector Instance { get; } = new();

    public IrBlob? Select(IReadOnlyList<IrBlob> blobs)
    {
        if (blobs is null || blobs.Count == 0)
        {
            return null;
        }

        IrBlob? best = null;
        double bestScore = double.NegativeInfinity;

        foreach (var blob in blobs)
        {
            var areaScore = Math.Max(0, blob.Area);
            var intensityScore = Math.Max(0, blob.Intensity);
            var confidenceScore = Math.Clamp(blob.Confidence, 0, 1);
            var score = (areaScore * 0.7) + (intensityScore * 0.2) + (confidenceScore * 0.1);

            if (score > bestScore)
            {
                bestScore = score;
                best = blob;
            }
        }

        return best;
    }
}

public interface IPointerDriver
{
    ValueTask MoveAsync(PixelCoordinate coordinate, CancellationToken cancellationToken = default);
}

public sealed class NullPointerDriver : IPointerDriver
{
    public static NullPointerDriver Instance { get; } = new();

    public ValueTask MoveAsync(PixelCoordinate coordinate, CancellationToken cancellationToken = default)
        => ValueTask.CompletedTask;
}

public static class PointerDriverFactory
{
    public static IPointerDriver CreateDefault()
        => OperatingSystem.IsWindows() ? new WindowsPointerDriver() : NullPointerDriver.Instance;
}

[SupportedOSPlatform("windows")]
public sealed class WindowsPointerDriver : IPointerDriver
{
    public ValueTask MoveAsync(PixelCoordinate coordinate, CancellationToken cancellationToken = default)
    {
        if (!OperatingSystem.IsWindows())
        {
            return ValueTask.CompletedTask;
        }

        var x = (int)Math.Round(coordinate.X);
        var y = (int)Math.Round(coordinate.Y);
        SetCursorPos(x, y);
        return ValueTask.CompletedTask;
    }

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetCursorPos(int x, int y);
}

public sealed class IrPointerPipeline
{
    private readonly HomographyMapping _mapping;
    private readonly IIrBlobSelector _selector;
    private readonly IPointerDriver _pointerDriver;

    public IrPointerPipeline(
        HomographyMapping mapping,
        IIrBlobSelector? selector = null,
        IPointerDriver? pointerDriver = null)
    {
        _mapping = mapping ?? throw new ArgumentNullException(nameof(mapping));
        _selector = selector ?? LargestBlobSelector.Instance;
        _pointerDriver = pointerDriver ?? NullPointerDriver.Instance;
    }

    public event Action<ProjectedPointerSample>? PointerProjected;

    public async ValueTask<ProjectedPointerSample?> ProcessFrameAsync(
        IrBlobFrame frame,
        CancellationToken cancellationToken = default)
    {
        if (frame is null)
        {
            throw new ArgumentNullException(nameof(frame));
        }

        var candidate = _selector.Select(frame.Blobs);
        if (candidate is null)
        {
            return null;
        }

        if (!_mapping.TryProject(candidate.Pixel, out var screenPixel))
        {
            return null;
        }

        var bounds = _mapping.ScreenBounds;
        var clampedPixel = new PixelCoordinate
        {
            X = Math.Clamp(screenPixel.X, 0, bounds.Width),
            Y = Math.Clamp(screenPixel.Y, 0, bounds.Height)
        };

        var normalized = new NormalizedCoordinate
        {
            X = bounds.Width <= 0 ? 0 : clampedPixel.X / bounds.Width,
            Y = bounds.Height <= 0 ? 0 : clampedPixel.Y / bounds.Height
        };

        var sample = new ProjectedPointerSample
        {
            ScreenPixel = clampedPixel,
            ScreenNormalized = normalized,
            SourceBlob = candidate,
            Timestamp = frame.Timestamp
        };

        await _pointerDriver.MoveAsync(clampedPixel, cancellationToken).ConfigureAwait(false);
        PointerProjected?.Invoke(sample);
        return sample;
    }
}
