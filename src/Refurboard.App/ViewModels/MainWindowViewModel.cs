using System;
using System.Linq;
using Refurboard.Core.Configuration;

namespace Refurboard.App.ViewModels;

public sealed class MainWindowViewModel
{
    public MainWindowViewModel(ConfigBootstrapResult result)
    {
        ConfigPath = result.ConfigPath;
        Locale = result.Validation.Locale;
        ShouldTriggerCalibration = result.ShouldTriggerCalibration;
        StatusMessage = result.Validation.IsValid ? "Configuration ready" : "Configuration requires attention";
        DetailMessage = result.Validation.IsValid
            ? $"Schema {result.Validation.ExpectedSchemaVersion} applied. Locale {Locale}."
            : string.Join(Environment.NewLine, result.Validation.Errors.DefaultIfEmpty("Unknown validation error."));
        NextSteps = result.Validation.IsValid
            ? (result.ShouldTriggerCalibration
                ? "Calibration workflow scheduled automatically."
                : "You can proceed to camera pairing when ready.")
            : result.Validation.RepairPlan.Message;
    }

    public string ConfigPath { get; }

    public string Locale { get; }

    public bool ShouldTriggerCalibration { get; }

    public string StatusMessage { get; }

    public string DetailMessage { get; }

    public string NextSteps { get; }
}
