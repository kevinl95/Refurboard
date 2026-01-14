using System;
using System.IO;
using System.Reflection;
using Json.Schema;

namespace Refurboard.Core.Configuration;

internal static class ConfigurationSchemaProvider
{
    private const string ResourceName = "Refurboard.Core.Configuration.config.schema.json";

    private static readonly Lazy<JsonSchema> Schema = new(() =>
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(ResourceName)
                           ?? throw new InvalidOperationException($"Embedded schema '{ResourceName}' could not be located.");
        using var reader = new StreamReader(stream);
        var text = reader.ReadToEnd();
        return JsonSchema.FromText(text);
    });

    public static JsonSchema GetSchema() => Schema.Value;
}
