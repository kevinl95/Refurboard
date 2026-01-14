using System;
using System.Collections.Generic;
using Refurboard.Core.Camera;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Vision.IrTracking;

public sealed class IrBlobDetector
{
    public IReadOnlyList<IrBlob> Detect(
        CameraFrame frame,
        ThresholdProfile? thresholds,
        int maxBlobs = 8)
    {
        if (frame is null)
        {
            throw new ArgumentNullException(nameof(frame));
        }

        if (frame.PixelFormat != CameraPixelFormat.Bgra8888)
        {
            throw new NotSupportedException("Only BGRA8888 pixel format is supported.");
        }

        thresholds ??= new ThresholdProfile();
        maxBlobs = Math.Clamp(maxBlobs, 1, 32);

        var intensityThreshold = Math.Clamp(thresholds.Intensity, 0, 1);
        var byteThreshold = (int)Math.Round(intensityThreshold * 255d);
        var minArea = thresholds.MinArea <= 0 ? 4 : thresholds.MinArea;
        var sampleStep = Math.Clamp((int)Math.Max(1, Math.Round(Math.Sqrt(minArea))), 1, 32);

        var buffer = frame.Buffer;
        var stride = frame.Stride;
        var width = frame.Width;
        var height = frame.Height;
        var candidates = new List<(double Intensity, IrBlob Blob)>();

        for (var y = 0; y < height; y += sampleStep)
        {
            var rowOffset = y * stride;
            for (var x = 0; x < width; x += sampleStep)
            {
                var offset = rowOffset + (x * 4);
                if (offset + 2 >= buffer.Length)
                {
                    break;
                }

                var b = buffer[offset];
                var g = buffer[offset + 1];
                var r = buffer[offset + 2];
                var intensity = (0.114 * b) + (0.587 * g) + (0.299 * r);
                if (intensity < byteThreshold)
                {
                    continue;
                }

                var blob = new IrBlob
                {
                    Pixel = new PixelCoordinate { X = x, Y = y },
                    Area = sampleStep * sampleStep,
                    Intensity = intensity / 255d,
                    Confidence = 0.9
                };

                candidates.Add((intensity, blob));
            }
        }

        if (candidates.Count == 0)
        {
            return Array.Empty<IrBlob>();
        }

        candidates.Sort((a, b) => b.Intensity.CompareTo(a.Intensity));
        var take = Math.Min(maxBlobs, candidates.Count);
        var blobs = new List<IrBlob>(take);
        for (var i = 0; i < take; i++)
        {
            blobs.Add(candidates[i].Blob);
        }

        return blobs;
    }
}
