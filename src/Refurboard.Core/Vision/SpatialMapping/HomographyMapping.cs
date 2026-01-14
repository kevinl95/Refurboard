using System;
using System.Collections.Generic;
using System.Linq;
using OpenCvSharp;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Vision.SpatialMapping;

/// <summary>
/// Represents a perspective homography that projects camera pixels into screen-space coordinates.
/// </summary>
public sealed class HomographyMapping
{
    private static readonly IReadOnlyDictionary<string, (double normalizedX, double normalizedY)> CornerTargets =
        new Dictionary<string, (double, double)>(StringComparer.OrdinalIgnoreCase)
        {
            ["TopLeft"] = (0d, 0d),
            ["TopRight"] = (1d, 0d),
            ["BottomRight"] = (1d, 1d),
            ["BottomLeft"] = (0d, 1d)
        };

    private static readonly string[] OrderedCornerNames =
    {
        "TopLeft",
        "TopRight",
        "BottomRight",
        "BottomLeft"
    };

    private readonly double[] _matrix; // 3x3 row-major matrix.
    private readonly double _epsilon;

    private HomographyMapping(double[] matrix, ScreenBounds screenBounds, double epsilon = 1e-6)
    {
        _matrix = matrix ?? throw new ArgumentNullException(nameof(matrix));
        ScreenBounds = screenBounds ?? throw new ArgumentNullException(nameof(screenBounds));
        _epsilon = epsilon;
    }

    public ScreenBounds ScreenBounds { get; }

    /// <summary>
    /// Attempts to project a camera pixel onto the calibrated screen surface.
    /// </summary>
    public bool TryProject(PixelCoordinate cameraPixel, out PixelCoordinate screenPixel)
    {
        if (cameraPixel is null)
        {
            throw new ArgumentNullException(nameof(cameraPixel));
        }

        var xPrime = _matrix[0] * cameraPixel.X + _matrix[1] * cameraPixel.Y + _matrix[2];
        var yPrime = _matrix[3] * cameraPixel.X + _matrix[4] * cameraPixel.Y + _matrix[5];
        var wPrime = _matrix[6] * cameraPixel.X + _matrix[7] * cameraPixel.Y + _matrix[8];

        if (Math.Abs(wPrime) < _epsilon)
        {
            screenPixel = default!;
            return false;
        }

        var w = 1d / wPrime;
        var projectedX = xPrime * w;
        var projectedY = yPrime * w;

        screenPixel = new PixelCoordinate
        {
            X = projectedX,
            Y = projectedY
        };

        return true;
    }

    /// <summary>
    /// Attempts to project a camera pixel and return the result normalized to the calibrated screen bounds (0-1).
    /// </summary>
    public bool TryProjectNormalized(PixelCoordinate cameraPixel, out NormalizedCoordinate normalized)
    {
        if (!TryProject(cameraPixel, out var screenPixel))
        {
            normalized = default!;
            return false;
        }

        var width = Math.Max(1, ScreenBounds.Width);
        var height = Math.Max(1, ScreenBounds.Height);

        normalized = new NormalizedCoordinate
        {
            X = screenPixel.X / width,
            Y = screenPixel.Y / height
        };

        return true;
    }

    public static bool TryCreate(CalibrationProfile calibration, out HomographyMapping mapping, out string? error)
    {
        mapping = default!;
        error = null;

        if (calibration is null)
        {
            error = "Calibration profile is missing.";
            return false;
        }

        if (calibration.Corners is null || calibration.Corners.Count < OrderedCornerNames.Length)
        {
            error = "Calibration profile does not include all four corner observations.";
            return false;
        }

        if (calibration.ScreenBoundsPx is null || calibration.ScreenBoundsPx.Width <= 0 || calibration.ScreenBoundsPx.Height <= 0)
        {
            error = "Calibration profile contains invalid screen dimensions.";
            return false;
        }

        var byName = calibration.Corners
            .GroupBy(c => c.Name, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(g => g.Key, g => g.Last(), StringComparer.OrdinalIgnoreCase);

        var cameraPoints = new Point2f[OrderedCornerNames.Length];
        var screenPoints = new Point2f[OrderedCornerNames.Length];

        for (var i = 0; i < OrderedCornerNames.Length; i++)
        {
            var name = OrderedCornerNames[i];
            if (!byName.TryGetValue(name, out var observation))
            {
                error = $"Calibration profile is missing the {name} corner.";
                return false;
            }

            cameraPoints[i] = new Point2f((float)(observation.Pixel?.X ?? 0d), (float)(observation.Pixel?.Y ?? 0d));

            var (nx, ny) = CornerTargets[name];
            var screenWidth = calibration.ScreenBoundsPx.Width;
            var screenHeight = calibration.ScreenBoundsPx.Height;
            screenPoints[i] = new Point2f((float)(nx * screenWidth), (float)(ny * screenHeight));
        }

        using var matrix = Cv2.GetPerspectiveTransform(cameraPoints, screenPoints);
        if (matrix.Empty())
        {
            error = "Homography computation returned an empty matrix.";
            return false;
        }

        var flattened = new double[9];
        for (var row = 0; row < 3; row++)
        {
            for (var col = 0; col < 3; col++)
            {
                flattened[row * 3 + col] = matrix.At<double>(row, col);
            }
        }

        mapping = new HomographyMapping(flattened, calibration.ScreenBoundsPx);
        return true;
    }
}
