using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Json.Schema;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Configuration;

public sealed class RefurboardConfigValidator
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    private readonly JsonSchema _schema;

    public RefurboardConfigValidator(JsonSchema? schema = null)
    {
        _schema = schema ?? ConfigurationSchemaProvider.GetSchema();
    }

    public ConfigValidationResult Validate(Stream jsonStream)
    {
        using var document = JsonDocument.Parse(jsonStream);
        return Validate(document.RootElement);
    }

    public ConfigValidationResult Validate(RefurboardConfig config)
    {
        var payload = JsonSerializer.SerializeToUtf8Bytes(config, SerializerOptions);
        using var document = JsonDocument.Parse(payload);
        return Validate(document.RootElement);
    }

    public ConfigValidationResult Validate(string json)
    {
        using var document = JsonDocument.Parse(json);
        return Validate(document.RootElement);
    }

    private ConfigValidationResult Validate(JsonElement root)
    {
        var evaluation = _schema.Evaluate(root, new EvaluationOptions { OutputFormat = OutputFormat.List });
        var schemaErrors = CollectSchemaErrors(evaluation);
        var schemaVersion = TryReadSchemaVersion(root);
        var locale = TryReadLocale(root) ?? "en-US";
        var requiresUpgrade = ConfigVersion.RequiresUpgrade(schemaVersion);
        var requiresCalibration = NeedsCalibration(root);

        if (requiresUpgrade)
        {
            schemaErrors.Add($"Schema {schemaVersion ?? "unknown"} is incompatible with required {ConfigVersion.SchemaString}.");
        }

        var isValid = evaluation.IsValid && schemaErrors.Count == 0 && !requiresUpgrade;
        RefurboardConfig? parsed = null;

        if (isValid)
        {
            parsed = root.Deserialize<RefurboardConfig>(SerializerOptions);
        }

        var repairPlan = BuildRepairPlan(schemaErrors, requiresUpgrade, requiresCalibration, locale);

        return new ConfigValidationResult(
            isValid,
            requiresUpgrade,
            requiresCalibration,
            schemaVersion,
            ConfigVersion.SchemaString,
            locale,
            schemaErrors,
            repairPlan,
            parsed);
    }

    private static List<string> CollectSchemaErrors(EvaluationResults evaluation)
    {
        if (evaluation.IsValid)
        {
            return new List<string>();
        }

        var errors = new List<string>();
        foreach (var detail in evaluation.Details)
        {
            if (!detail.HasErrors || detail.Errors is null)
            {
                continue;
            }

            foreach (var kvp in detail.Errors)
            {
                errors.Add($"{detail.InstanceLocation}: {kvp.Value}");
            }
        }

        return errors;
    }

    private static bool NeedsCalibration(JsonElement root)
    {
        if (!root.TryGetProperty("calibration", out var calibration))
        {
            return true;
        }

        if (!calibration.TryGetProperty("corners", out var corners) || corners.ValueKind != JsonValueKind.Array)
        {
            return true;
        }

        var counter = 0;
        foreach (var _ in corners.EnumerateArray())
        {
            counter++;
        }

        if (counter < 4)
        {
            return true;
        }

        return corners.EnumerateArray().Any(corner =>
            !corner.TryGetProperty("pixel", out var pixel) ||
            !pixel.TryGetProperty("x", out _) ||
            !pixel.TryGetProperty("y", out _));
    }

    private static string? TryReadSchemaVersion(JsonElement root)
    {
        return root.TryGetProperty("metadata", out var metadata) &&
               metadata.TryGetProperty("schemaVersion", out var value)
            ? value.GetString()
            : null;
    }

    private static string? TryReadLocale(JsonElement root)
    {
        return root.TryGetProperty("metadata", out var metadata) &&
               metadata.TryGetProperty("locale", out var value)
            ? value.GetString()
            : null;
    }

    private static ConfigRepairPlan BuildRepairPlan(
        IReadOnlyCollection<string> errors,
        bool requiresUpgrade,
        bool requiresCalibration,
        string locale)
    {
        if (requiresUpgrade)
        {
            return new ConfigRepairPlan(true, true, locale == "en-US", "Configuration schema needs to be upgraded and calibration must be re-run.");
        }

        if (requiresCalibration)
        {
            return new ConfigRepairPlan(false, true, false, "Calibration data is incomplete. Launch calibration workflow.");
        }

        if (errors.Count > 0)
        {
            return new ConfigRepairPlan(true, true, true, "Configuration failed schema validation and will be regenerated.");
        }

        return ConfigRepairPlan.None;
    }
}
