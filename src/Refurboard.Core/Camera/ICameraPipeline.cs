using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace Refurboard.Core.Camera;

public interface ICameraPipeline : IAsyncDisposable
{
    event EventHandler<CameraFrameArrivedEventArgs>? FrameArrived;
    event EventHandler<CameraStatusChangedEventArgs>? StatusChanged;

    CameraDeviceDescriptor? ActiveDevice { get; }

    CameraStatus Status { get; }

    Task<IReadOnlyList<CameraDeviceDescriptor>> EnumerateDevicesAsync(int maxDevices = 6, CancellationToken cancellationToken = default);

    Task StartAsync(CameraCaptureRequest request, CancellationToken cancellationToken = default);

    Task StopAsync(CancellationToken cancellationToken = default);
}
