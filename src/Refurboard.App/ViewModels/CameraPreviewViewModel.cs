using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Threading;
using Refurboard.Core.Camera;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.App.ViewModels;

public sealed class CameraPreviewViewModel : ViewModelBase, IAsyncDisposable
{
    private readonly CameraProfile _profile;
    private readonly OpenCvCameraPipeline _pipeline = new();
    private readonly SemaphoreSlim _lifecycleGate = new(1, 1);
    private CancellationTokenSource? _cts;
    private Bitmap? _frame;
    private string _statusText = "Initializing camera...";
    private string _deviceName = "Auto";
    private bool _isStreaming;

    public CameraPreviewViewModel(CameraProfile? profile)
    {
        _profile = profile ?? new CameraProfile();
    }

    public Bitmap? Frame => _frame;

    public string StatusText
    {
        get => _statusText;
        private set => SetProperty(ref _statusText, value);
    }

    public string DeviceName
    {
        get => _deviceName;
        private set => SetProperty(ref _deviceName, value);
    }

    public bool IsStreaming
    {
        get => _isStreaming;
        private set => SetProperty(ref _isStreaming, value);
    }

    public string? ActiveDeviceFingerprint => _pipeline.ActiveDevice?.DeviceId;

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        await _lifecycleGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_cts is not null)
            {
                return;
            }

            await StartInternalAsync(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    public async Task RestartAsync(CancellationToken cancellationToken = default)
    {
        await _lifecycleGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await StopInternalAsync(cancellationToken).ConfigureAwait(false);
            await StartInternalAsync(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await _lifecycleGate.WaitAsync().ConfigureAwait(false);
        try
        {
            await StopInternalAsync().ConfigureAwait(false);
            await _pipeline.DisposeAsync().ConfigureAwait(false);
        }
        finally
        {
            _lifecycleGate.Release();
        }

        SwapFrame(null);
    }

    private async Task StartInternalAsync(CancellationToken cancellationToken)
    {
        _cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        _pipeline.FrameArrived += OnFrameArrived;
        _pipeline.StatusChanged += OnStatusChanged;
        await _pipeline.StartAsync(CameraCaptureRequest.FromProfile(_profile), _cts.Token).ConfigureAwait(false);
    }

    private async Task StopInternalAsync(CancellationToken cancellationToken = default)
    {
        if (_cts is null)
        {
            return;
        }

        _cts.Cancel();
        await _pipeline.StopAsync(cancellationToken).ConfigureAwait(false);
        _cts.Dispose();
        _cts = null;
        _pipeline.FrameArrived -= OnFrameArrived;
        _pipeline.StatusChanged -= OnStatusChanged;
        Dispatcher.UIThread.Post(() => SwapFrame(null));
        Dispatcher.UIThread.Post(() => IsStreaming = false);
    }

    private void OnFrameArrived(object? sender, CameraFrameArrivedEventArgs e)
    {
        try
        {
            var bitmap = CreateBitmap(e.Frame);
            Dispatcher.UIThread.Post(() => SwapFrame(bitmap));
        }
        catch
        {
            // Swallow frame conversion errors but keep pipeline alive.
        }
    }

    private void OnStatusChanged(object? sender, CameraStatusChangedEventArgs e)
    {
        Dispatcher.UIThread.Post(() =>
        {
            StatusText = e.Message;
            DeviceName = e.Device?.DisplayName ?? "Auto";
            IsStreaming = e.Status == CameraStatus.Streaming;
        });
    }

    private static Bitmap CreateBitmap(CameraFrame frame)
    {
        var bitmap = new WriteableBitmap(
            new PixelSize(frame.Width, frame.Height),
            new Vector(96, 96),
            PixelFormat.Bgra8888,
            AlphaFormat.Unpremul);

        using var fb = bitmap.Lock();
        Marshal.Copy(frame.Buffer, 0, fb.Address, frame.Buffer.Length);
        return bitmap;
    }

    private void SwapFrame(Bitmap? next)
    {
        var previous = _frame;
        _frame = next;
        RaisePropertyChanged(nameof(Frame));
        previous?.Dispose();
    }
}
