using System;

namespace Refurboard.Core.Configuration;

public static class ConfigVersion
{
    public const string SchemaString = "1.0.0";
    public const string AppVersionString = "0.1.0-alpha";

    public static readonly Version Schema = Version.Parse(SchemaString);
    public static readonly Version App = Version.Parse(AppVersionString);

    public static bool IsMatch(string? candidate) =>
        Version.TryParse(candidate, out var parsed) && parsed == Schema;

    public static bool RequiresUpgrade(string? candidate)
    {
        if (!Version.TryParse(candidate, out var parsed))
        {
            return true;
        }

        return parsed < Schema;
    }
}
