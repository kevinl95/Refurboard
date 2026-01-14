using System;
using System.Globalization;
using System.Text.Json;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Configuration;

public static class ConfigurationTemplateFactory
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public static RefurboardConfig Create(string locale)
    {
        var normalizedLocale = string.IsNullOrWhiteSpace(locale) ? "en-US" : locale;
        return new RefurboardConfig
        {
            Metadata = new ConfigMetadata
            {
                Locale = normalizedLocale,
                LastUpdatedUtc = DateTimeOffset.UtcNow
            },
            Camera = new CameraProfile
            {
                DeviceId = "auto",
                FriendlyName = "Auto-Detected",
                Resolution = new CameraResolution { Width = 1280, Height = 720 },
                FrameRate = 30,
                FieldOfViewDegrees = 78,
                IsMirrored = false,
                Exposure = new ExposureProfile
                {
                    Mode = "Auto",
                    TargetLuma = 0.55,
                    ShutterMicroseconds = null
                },
                Thresholds = new ThresholdProfile
                {
                    Intensity = 0.82,
                    MinArea = 6,
                    MaxArea = 225
                }
            },
            Calibration = new CalibrationProfile
            {
                ScreenBoundsPx = new ScreenBounds { Width = 1920, Height = 1080 },
                Corners = new()
            }
        };
    }

    public static string Serialize(RefurboardConfig config) =>
        JsonSerializer.Serialize(config, SerializerOptions);

    public static RefurboardConfig CreateFromLocaleOrCulture(string? locale)
    {
        if (!string.IsNullOrWhiteSpace(locale))
        {
            return Create(locale);
        }

        var culture = CultureInfo.CurrentUICulture?.Name ?? "en-US";
        return Create(culture);
    }
}
