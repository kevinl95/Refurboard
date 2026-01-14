using System;
using System.Globalization;
using Refurboard.Core.Configuration;

namespace Refurboard.App.Startup;

internal static class BootstrapState
{
    public static ConfigBootstrapResult Result { get; private set; } = ConfigBootstrapResult.Empty;

    public static void Initialize()
    {
        var locale = CultureInfo.CurrentUICulture?.Name ?? "en-US";
        var bootstrapper = new ConfigurationBootstrapper();
        Result = bootstrapper.EnsureOnDisk(preferredLocale: locale);
        Console.WriteLine(Result.Summary);
    }
}
