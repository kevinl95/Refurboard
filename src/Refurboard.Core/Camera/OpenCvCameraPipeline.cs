using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using OpenCvSharp;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Camera;

public sealed class OpenCvCameraPipeline : ICameraPipeline
{
    private static readonly CameraResolution[] ResolutionFallbacks =
    {
        new() { Width = 1280, Height = 720 },
        new() { Width = 1920, Height = 1080 },
        new() { Width = 640, Height = 480 }
    };

    private const int MaxProbeDevices = 6;

    private CancellationTokenSource? _cts;
    private Task? _captureLoop;
    private CameraCaptureRequest? _request;

    public event EventHandler<CameraFrameArrivedEventArgs>? FrameArrived;
    public event EventHandler<CameraStatusChangedEventArgs>? StatusChanged;

    public CameraDeviceDescriptor? ActiveDevice { get; private set; }

    public CameraStatus Status { get; private set; } = CameraStatus.Idle;

    public Task<IReadOnlyList<CameraDeviceDescriptor>> EnumerateDevicesAsync(
        int maxDevices = MaxProbeDevices,
        CancellationToken cancellationToken = default)
    {
        var devices = new List<CameraDeviceDescriptor>();

        for (var index = 0; index < maxDevices; index++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            using var capture = new VideoCapture(index, VideoCaptureAPIs.ANY);
            if (!capture.IsOpened())
            {
                continue;
            }

            var width = SafeDimension((int)capture.Get(VideoCaptureProperties.FrameWidth), 640);
            var height = SafeDimension((int)capture.Get(VideoCaptureProperties.FrameHeight), 480);
            devices.Add(CameraDeviceDescriptor.Create(index, new CameraResolution { Width = width, Height = height }));
        }

        return Task.FromResult<IReadOnlyList<CameraDeviceDescriptor>>(devices);
    }

    public async Task StartAsync(CameraCaptureRequest request, CancellationToken cancellationToken = default)
    {
        await StopAsync(cancellationToken).ConfigureAwait(false);

        _request = request;
        _cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        _captureLoop = Task.Run(() => RunLoopAsync(request, _cts.Token), CancellationToken.None);
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (_cts is null)
        {
            return;
        }

        _cts.Cancel();

        if (_captureLoop is not null)
        {
            var completion = _captureLoop;
            await Task.WhenAny(completion, Task.Delay(TimeSpan.FromSeconds(2), cancellationToken)).ConfigureAwait(false);
        }

        _cts.Dispose();
        _cts = null;
        _captureLoop = null;
        ActiveDevice = null;
        UpdateStatus(CameraStatus.Idle, "Camera idle.");
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync().ConfigureAwait(false);
    }

    private async Task RunLoopAsync(CameraCaptureRequest request, CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                UpdateStatus(CameraStatus.Searching, "Searching for camera devices...");
                var device = await ResolveDeviceAsync(request.DeviceId, cancellationToken).ConfigureAwait(false);

                if (device is null)
                {
                    UpdateStatus(CameraStatus.Error, "No cameras detected. Retrying...");
                    await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken).ConfigureAwait(false);
                    continue;
                }

                if (device.Index < 0)
                {
                    device = device with { Index = 0 };
                }

                using var capture = new VideoCapture(device.Index, VideoCaptureAPIs.ANY);
                if (!capture.IsOpened())
                {
                    ActiveDevice = null;
                    UpdateStatus(CameraStatus.Disconnected, $"Unable to open {device.DisplayName}. Retrying...");
                    await Task.Delay(TimeSpan.FromSeconds(1.5), cancellationToken).ConfigureAwait(false);
                    continue;
                }

                ActiveDevice = device;
                var appliedResolution = ApplyResolution(capture, request.Resolution);
                var appliedFps = ApplyFrameRate(capture, request.FrameRate);
                UpdateStatus(CameraStatus.Streaming,
                    $"{device.DisplayName} @ {appliedResolution.Width}x{appliedResolution.Height} ({appliedFps:0.#} fps)");

                var keepStreaming = await CaptureLoopAsync(capture, request, cancellationToken).ConfigureAwait(false);
                if (!keepStreaming)
                {
                    ActiveDevice = null;
                    UpdateStatus(CameraStatus.Disconnected, "Camera feed interrupted. Reconnecting...");
                    await Task.Delay(TimeSpan.FromMilliseconds(350), cancellationToken).ConfigureAwait(false);
                }
            }
        }
        catch (OperationCanceledException)
        {
            UpdateStatus(CameraStatus.Idle, "Camera idle.");
        }
        catch (Exception ex)
        {
            UpdateStatus(CameraStatus.Error, $"Camera pipeline error: {ex.Message}");
        }
    }

    private async Task<CameraDeviceDescriptor?> ResolveDeviceAsync(string deviceId, CancellationToken cancellationToken)
    {
        var devices = await EnumerateDevicesAsync(MaxProbeDevices, cancellationToken).ConfigureAwait(false);
        if (devices.Count == 0)
        {
            return null;
        }

        if (string.Equals(deviceId, "auto", StringComparison.OrdinalIgnoreCase))
        {
            return devices[0];
        }

        return devices.FirstOrDefault(d => string.Equals(d.DeviceId, deviceId, StringComparison.OrdinalIgnoreCase)) ?? devices[0];
    }

    private static CameraResolution ApplyResolution(VideoCapture capture, CameraResolution preferred)
    {
        foreach (var candidate in EnumerateCandidates(preferred))
        {
            capture.Set(VideoCaptureProperties.FrameWidth, candidate.Width);
            capture.Set(VideoCaptureProperties.FrameHeight, candidate.Height);

            var actualWidth = SafeDimension((int)capture.Get(VideoCaptureProperties.FrameWidth), candidate.Width);
            var actualHeight = SafeDimension((int)capture.Get(VideoCaptureProperties.FrameHeight), candidate.Height);

            if (Math.Abs(actualWidth - candidate.Width) <= 4 && Math.Abs(actualHeight - candidate.Height) <= 4)
            {
                return new CameraResolution { Width = actualWidth, Height = actualHeight };
            }
        }

        return new CameraResolution
        {
            Width = SafeDimension((int)capture.Get(VideoCaptureProperties.FrameWidth), preferred.Width),
            Height = SafeDimension((int)capture.Get(VideoCaptureProperties.FrameHeight), preferred.Height)
        };
    }

    private static IEnumerable<CameraResolution> EnumerateCandidates(CameraResolution preferred)
    {
        yield return preferred;
        foreach (var fallback in ResolutionFallbacks)
        {
            if (fallback.Width == preferred.Width && fallback.Height == preferred.Height)
            {
                continue;
            }

            yield return fallback;
        }
    }

    private static double ApplyFrameRate(VideoCapture capture, double preferredFps)
    {
        if (preferredFps <= 0)
        {
            preferredFps = 30d;
        }

        capture.Set(VideoCaptureProperties.Fps, preferredFps);
        var actual = capture.Get(VideoCaptureProperties.Fps);
        return actual <= 0 ? preferredFps : actual;
    }

    private async Task<bool> CaptureLoopAsync(VideoCapture capture, CameraCaptureRequest request, CancellationToken cancellationToken)
    {
        var failureCount = 0;
        while (!cancellationToken.IsCancellationRequested)
        {
            using var mat = new Mat();
            if (!capture.Read(mat) || mat.Empty())
            {
                failureCount++;
                if (failureCount > 15)
                {
                    return false;
                }

                await Task.Delay(TimeSpan.FromMilliseconds(80), cancellationToken).ConfigureAwait(false);
                continue;
            }

            failureCount = 0;
            var frame = ConvertFrame(mat, request.IsMirrored);
            FrameArrived?.Invoke(this, new CameraFrameArrivedEventArgs(frame));
        }

        return true;
    }

    private static CameraFrame ConvertFrame(Mat source, bool mirror)
    {
        Mat working = source;
        Mat? mirrorBuffer = null;

        if (mirror)
        {
            mirrorBuffer = new Mat();
            Cv2.Flip(source, mirrorBuffer, FlipMode.Y);
            working = mirrorBuffer;
        }

        using var bgra = new Mat();
        Cv2.CvtColor(working, bgra, ColorConversionCodes.BGR2BGRA);
        var stride = (int)bgra.Step();
        var length = stride * bgra.Rows;
        var buffer = new byte[length];
        Marshal.Copy(bgra.Data, buffer, 0, length);

        mirrorBuffer?.Dispose();

        return new CameraFrame(CameraPixelFormat.Bgra8888, bgra.Width, bgra.Height, stride, buffer, DateTimeOffset.UtcNow);
    }

    private void UpdateStatus(CameraStatus status, string message)
    {
        Status = status;
        StatusChanged?.Invoke(this, new CameraStatusChangedEventArgs(status, message, ActiveDevice));
    }

    private static int SafeDimension(int value, int fallback)
        => value <= 0 ? fallback : value;
}
