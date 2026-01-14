using System;

namespace Refurboard.Core.Configuration;

public sealed record class ConfigBootstrapResult(
    string ConfigPath,
    ConfigValidationResult Validation,
    bool ConfigFileCreated,
    DateTimeOffset CompletedAtUtc)
{
    public static ConfigBootstrapResult Empty { get; } = new(
        "(not-initialized)",
        ConfigValidationResult.Invalid("Configuration has not been bootstrapped."),
        false,
        DateTimeOffset.MinValue);

    public bool ShouldTriggerCalibration => ConfigFileCreated || Validation.RequiresCalibration;

    public string Summary => Validation.IsValid
        ? $"Configuration ready at {ConfigPath} (locale {Validation.Locale})."
        : $"Configuration requires attention: {string.Join("; ", Validation.Errors)}";
}
