using System;
using System.Collections.Generic;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Configuration;

public sealed record class ConfigValidationResult(
    bool IsValid,
    bool RequiresUpgrade,
    bool RequiresCalibration,
    string? DetectedSchemaVersion,
    string ExpectedSchemaVersion,
    string Locale,
    IReadOnlyList<string> Errors,
    ConfigRepairPlan RepairPlan,
    RefurboardConfig? ParsedConfig)
{
    public static ConfigValidationResult Invalid(string message, string locale = "en-US") =>
        new(false, true, true, null, ConfigVersion.SchemaString, locale,
            new List<string> { message },
            new ConfigRepairPlan(true, true, true, message), null);
}
