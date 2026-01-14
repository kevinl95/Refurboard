using System;
using System.IO;
using System.Text.Json;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Configuration;

public static class ConfigurationPersistence
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public static void Save(string path, RefurboardConfig config)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ArgumentException("Config path must be provided", nameof(path));
        }

        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var payload = JsonSerializer.Serialize(config, SerializerOptions);
        File.WriteAllText(path, payload);
    }
}
