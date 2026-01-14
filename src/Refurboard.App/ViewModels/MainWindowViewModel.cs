using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Refurboard.App.Calibration;
using Refurboard.Core.Configuration;
using Refurboard.Core.Configuration.Models;
using Refurboard.Core.Vision.IrTracking;
using Refurboard.Core.Vision.SpatialMapping;

namespace Refurboard.App.ViewModels;

public sealed class MainWindowViewModel : ViewModelBase, IAsyncDisposable
{
    private RefurboardConfig _config;
    private bool _shouldTriggerCalibration;
    private string _statusMessage = string.Empty;
    private string _detailMessage = string.Empty;
    private string _nextSteps = string.Empty;
    private bool _showCalibrationOverlay = true;
    private HomographyMapping? _homography;
    private string _homographyStatus = "Waiting for calibration";
    private IrPointerPipeline? _pointerPipeline;
    private string _pointerStatus = "Pointer pipeline idle.";
    private ProjectedPointerSample? _lastPointerSample;

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
        RefreshHomographyMapping();
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

    public IReadOnlyList<CornerObservation> CalibratedCorners =>
        (IReadOnlyList<CornerObservation>?)_config.Calibration?.Corners ?? Array.Empty<CornerObservation>();

    public bool ShowCalibrationOverlay
    {
        get => _showCalibrationOverlay;
        set => SetProperty(ref _showCalibrationOverlay, value);
    }

    public HomographyMapping? Homography => _homography;

    public bool HasHomographyMapping => _homography is not null;

    public string HomographyStatus
    {
        get => _homographyStatus;
        private set => SetProperty(ref _homographyStatus, value);
    }

    public string PointerStatus
    {
        get => _pointerStatus;
        private set => SetProperty(ref _pointerStatus, value);
    }

    public ProjectedPointerSample? LastPointerSample
    {
        get => _lastPointerSample;
        private set => SetProperty(ref _lastPointerSample, value);
    }

    public Task InitializeAsync(CancellationToken cancellationToken = default)
        => CameraPreview.StartAsync(cancellationToken);

    public async ValueTask DisposeAsync()
    {
        DetachPointerPipeline();
        await CameraPreview.DisposeAsync().ConfigureAwait(false);
    }

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
        RaisePropertyChanged(nameof(CalibratedCorners));
        RefreshHomographyMapping();
    }

    public async ValueTask<ProjectedPointerSample?> ProcessIrBlobsAsync(
        IReadOnlyList<IrBlob> blobs,
        CancellationToken cancellationToken = default)
    {
        if (blobs is null)
        {
            throw new ArgumentNullException(nameof(blobs));
        }

        var pipeline = _pointerPipeline;
        if (pipeline is null)
        {
            PointerStatus = "Pointer pipeline unavailable (no mapping).";
            return null;
        }

        if (blobs.Count == 0)
        {
            PointerStatus = "Waiting for IR blobs...";
            return null;
        }

        var frame = new IrBlobFrame
        {
            Timestamp = DateTimeOffset.UtcNow,
            Blobs = blobs
        };

        var sample = await pipeline.ProcessFrameAsync(frame, cancellationToken).ConfigureAwait(false);
        if (sample is null)
        {
            PointerStatus = "Tracking lost (projection failed).";
        }

        return sample;
    }

    public bool TryProjectCameraPoint(PixelCoordinate cameraPixel, out PixelCoordinate screenPixel)
    {
        if (cameraPixel is null)
        {
            throw new ArgumentNullException(nameof(cameraPixel));
        }

        if (_homography is null)
        {
            screenPixel = default!;
            return false;
        }

        return _homography.TryProject(cameraPixel, out screenPixel);
    }

    public bool TryProjectCameraPointNormalized(PixelCoordinate cameraPixel, out NormalizedCoordinate normalized)
    {
        if (cameraPixel is null)
        {
            throw new ArgumentNullException(nameof(cameraPixel));
        }

        if (_homography is null)
        {
            normalized = default!;
            return false;
        }

        return _homography.TryProjectNormalized(cameraPixel, out normalized);
    }

    private void RefreshHomographyMapping()
    {
        DetachPointerPipeline();

        if (_config.Calibration is null)
        {
            _homography = null;
            HomographyStatus = "Calibration profile missing.";
            PointerStatus = "Pointer pipeline idle (no calibration).";
            RaisePropertyChanged(nameof(Homography));
            RaisePropertyChanged(nameof(HasHomographyMapping));
            return;
        }

        if (HomographyMapping.TryCreate(_config.Calibration, out var mapping, out var error))
        {
            _homography = mapping;
            HomographyStatus = $"Mapping ready for {mapping.ScreenBounds.Width}x{mapping.ScreenBounds.Height}.";
            _pointerPipeline = new IrPointerPipeline(mapping, pointerDriver: PointerDriverFactory.CreateDefault());
            _pointerPipeline.PointerProjected += OnPointerProjected;
            PointerStatus = "Pointer pipeline ready.";
        }
        else
        {
            _homography = null;
            HomographyStatus = error ?? "Mapping unavailable.";
            PointerStatus = "Pointer pipeline idle (mapping error).";
        }

        RaisePropertyChanged(nameof(Homography));
        RaisePropertyChanged(nameof(HasHomographyMapping));
    }

    private void OnPointerProjected(ProjectedPointerSample sample)
    {
        LastPointerSample = sample;
        PointerStatus = $"Pointer projected at ({sample.ScreenPixel.X:F0}, {sample.ScreenPixel.Y:F0}).";
    }

    private void DetachPointerPipeline()
    {
        if (_pointerPipeline is not null)
        {
            _pointerPipeline.PointerProjected -= OnPointerProjected;
        }

        _pointerPipeline = null;
    }
}
