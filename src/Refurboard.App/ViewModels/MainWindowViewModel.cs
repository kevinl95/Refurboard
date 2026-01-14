using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Refurboard.Core.Configuration;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.App.ViewModels;

public sealed class MainWindowViewModel : ViewModelBase, IAsyncDisposable
{
    private readonly RefurboardConfig _config;

    public MainWindowViewModel(ConfigBootstrapResult result)
    {
        _config = result.Validation.ParsedConfig ?? new RefurboardConfig();
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

        CameraPreview = new CameraPreviewViewModel(_config.Camera);
    }

    public string ConfigPath { get; }

    public string Locale { get; }

    public bool ShouldTriggerCalibration { get; }

    public string StatusMessage { get; }

    public string DetailMessage { get; }

    public string NextSteps { get; }

    public CameraPreviewViewModel CameraPreview { get; }

    public Task InitializeAsync(CancellationToken cancellationToken = default)
        => CameraPreview.StartAsync(cancellationToken);

    public ValueTask DisposeAsync()
        => CameraPreview.DisposeAsync();
}
