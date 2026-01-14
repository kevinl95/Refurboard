using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;
using Refurboard.Core.Configuration;

namespace Refurboard.Core.Configuration.Models;

public sealed record class RefurboardConfig
{
    [JsonPropertyName("metadata")]
    public ConfigMetadata Metadata { get; init; } = new();

    [JsonPropertyName("camera")]
    public CameraProfile Camera { get; init; } = new();

    [JsonPropertyName("calibration")]
    public CalibrationProfile Calibration { get; init; } = new();
}

public sealed record class ConfigMetadata
{
    [JsonPropertyName("schemaVersion")]
    public string SchemaVersion { get; init; } = ConfigVersion.SchemaString;

    [JsonPropertyName("appVersion")]
    public string AppVersion { get; init; } = ConfigVersion.AppVersionString;

    [JsonPropertyName("lastUpdatedUtc")]
    public DateTimeOffset LastUpdatedUtc { get; init; } = DateTimeOffset.UtcNow;

    [JsonPropertyName("locale")]
    public string Locale { get; init; } = "en-US";
}

public sealed record class CameraProfile
{
    [JsonPropertyName("deviceId")]
    public string DeviceId { get; init; } = "auto";

    [JsonPropertyName("friendlyName")]
    public string FriendlyName { get; init; } = "Auto-Detected";

    [JsonPropertyName("resolution")]
    public CameraResolution Resolution { get; init; } = new();

    [JsonPropertyName("frameRate")]
    public double FrameRate { get; init; } = 30d;

    [JsonPropertyName("fieldOfViewDegrees")]
    public double FieldOfViewDegrees { get; init; } = 78d;

    [JsonPropertyName("isMirrored")]
    public bool IsMirrored { get; init; }

    [JsonPropertyName("exposure")]
    public ExposureProfile Exposure { get; init; } = new();

    [JsonPropertyName("thresholds")]
    public ThresholdProfile Thresholds { get; init; } = new();
}

public sealed record class CameraResolution
{
    [JsonPropertyName("width")]
    public int Width { get; init; } = 1280;

    [JsonPropertyName("height")]
    public int Height { get; init; } = 720;
}

public sealed record class ExposureProfile
{
    [JsonPropertyName("mode")]
    public string Mode { get; init; } = "Auto";

    [JsonPropertyName("targetLuma")]
    public double? TargetLuma { get; init; } = 0.5;

    [JsonPropertyName("shutterMicroseconds")]
    public double? ShutterMicroseconds { get; init; }
}

public sealed record class ThresholdProfile
{
    [JsonPropertyName("intensity")]
    public double Intensity { get; init; } = 0.85;

    [JsonPropertyName("minArea")]
    public double MinArea { get; init; } = 4;

    [JsonPropertyName("maxArea")]
    public double MaxArea { get; init; } = 250;
}

public sealed record class CalibrationProfile
{
    [JsonPropertyName("corners")]
    public List<CornerObservation> Corners { get; init; } = new();

    [JsonPropertyName("screenBoundsPx")]
    public ScreenBounds ScreenBoundsPx { get; init; } = new();

    [JsonPropertyName("completedAtUtc")]
    public DateTimeOffset? CompletedAtUtc { get; init; }

    [JsonPropertyName("deviceFingerprint")]
    public string? DeviceFingerprint { get; init; }
}

public sealed record class ScreenBounds
{
    [JsonPropertyName("width")]
    public int Width { get; init; } = 1920;

    [JsonPropertyName("height")]
    public int Height { get; init; } = 1080;
}

public sealed record class CornerObservation
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = "TopLeft";

    [JsonPropertyName("pixel")]
    public PixelCoordinate Pixel { get; init; } = new();

    [JsonPropertyName("normalized")]
    public NormalizedCoordinate Normalized { get; init; } = new();
}

public sealed record class PixelCoordinate
{
    [JsonPropertyName("x")]
    public double X { get; init; }

    [JsonPropertyName("y")]
    public double Y { get; init; }
}

public sealed record class NormalizedCoordinate
{
    [JsonPropertyName("x")]
    public double X { get; init; }

    [JsonPropertyName("y")]
    public double Y { get; init; }
}
