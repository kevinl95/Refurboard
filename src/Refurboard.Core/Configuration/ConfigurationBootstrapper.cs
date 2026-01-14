using System;
using System.Globalization;
using System.IO;
using System.Threading;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Configuration;

public sealed class ConfigurationBootstrapper
{
    private readonly RefurboardConfigValidator _validator;

    public ConfigurationBootstrapper(RefurboardConfigValidator? validator = null)
    {
        _validator = validator ?? new RefurboardConfigValidator();
    }

    public ConfigBootstrapResult EnsureOnDisk(
        string? rootDirectory = null,
        string? preferredLocale = null,
        CancellationToken cancellationToken = default)
    {
        var locale = string.IsNullOrWhiteSpace(preferredLocale)
            ? CultureInfo.CurrentUICulture?.Name ?? "en-US"
            : preferredLocale;

        var directory = rootDirectory ?? ResolveDefaultRootDirectory();
        Directory.CreateDirectory(directory);

        var path = Path.Combine(directory, "refurboard.config.json");
        if (!File.Exists(path))
        {
            var template = ConfigurationTemplateFactory.Create(locale);
            Persist(path, template, cancellationToken);
            var validation = _validator.Validate(template);
            return new ConfigBootstrapResult(path, validation, true, DateTimeOffset.UtcNow);
        }

        using var stream = File.OpenRead(path);
        var existingValidation = _validator.Validate(stream);
        if (existingValidation.IsValid)
        {
            return new ConfigBootstrapResult(path, existingValidation, false, DateTimeOffset.UtcNow);
        }

        if (!existingValidation.RequiresUpgrade && existingValidation.Errors.Count == 0)
        {
            return new ConfigBootstrapResult(path, existingValidation, false, DateTimeOffset.UtcNow);
        }

        var replacement = ConfigurationTemplateFactory.Create(existingValidation.Locale);
        Persist(path, replacement, cancellationToken);
        var repairedValidation = _validator.Validate(replacement);
        return new ConfigBootstrapResult(path, repairedValidation, true, DateTimeOffset.UtcNow);
    }

    public static string ResolveDefaultRootDirectory()
    {
        if (OperatingSystem.IsWindows())
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Refurboard");
        }

        if (OperatingSystem.IsMacOS())
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Personal), "Library", "Application Support", "Refurboard");
        }

        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".config", "Refurboard");
    }

    private static void Persist(string path, RefurboardConfig config, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ArgumentException("Path must be provided", nameof(path));
        }

        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        cancellationToken.ThrowIfCancellationRequested();
        var payload = ConfigurationTemplateFactory.Serialize(config);
        File.WriteAllText(path, payload);
    }
}
