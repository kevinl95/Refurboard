using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Refurboard.App.Calibration;
using Refurboard.Core.Configuration;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.App.ViewModels;

public sealed class MainWindowViewModel : ViewModelBase, IAsyncDisposable
{
    private RefurboardConfig _config;
    private bool _shouldTriggerCalibration;
    private string _statusMessage = string.Empty;
    private string _detailMessage = string.Empty;
    private string _nextSteps = string.Empty;

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

    public bool ShouldTriggerCalibration
    {
        get => _shouldTriggerCalibration;
        private set => SetProperty(ref _shouldTriggerCalibration, value);
    }

    public string StatusMessage
    {
        get => _statusMessage;
        private set => SetProperty(ref _statusMessage, value);
    }

    public string DetailMessage
    {
        get => _detailMessage;
        private set => SetProperty(ref _detailMessage, value);
    }

    public string NextSteps
    {
        get => _nextSteps;
        private set => SetProperty(ref _nextSteps, value);
    }

    public CameraPreviewViewModel CameraPreview { get; }

    public Task InitializeAsync(CancellationToken cancellationToken = default)
        => CameraPreview.StartAsync(cancellationToken);

    public ValueTask DisposeAsync()
        => CameraPreview.DisposeAsync();

    public async Task ApplyCalibrationAsync(CalibrationOutcome outcome, CancellationToken cancellationToken = default)
    {
        if (outcome is null)
        {
            throw new ArgumentNullException(nameof(outcome));
        }

        var updatedCalibration = new CalibrationProfile
        {
            Corners = outcome.Corners.ToList(),
            ScreenBoundsPx = new ScreenBounds
            {
                Width = outcome.ScreenWidth,
                Height = outcome.ScreenHeight
            },
            CompletedAtUtc = DateTimeOffset.UtcNow,
            DeviceFingerprint = CameraPreview.ActiveDeviceFingerprint
        };

        _config = _config with { Calibration = updatedCalibration };

        await Task.Run(() => ConfigurationPersistence.Save(ConfigPath, _config), cancellationToken).ConfigureAwait(false);

        ShouldTriggerCalibration = false;
        StatusMessage = "Configuration ready";
        DetailMessage = $"Calibration captured for {outcome.ScreenWidth}x{outcome.ScreenHeight} at {DateTimeOffset.UtcNow:HH:mm:ss}.";
        NextSteps = "Camera + IR detection can now align to the calibrated surface.";
    }
}
