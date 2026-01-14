using System;
using System.Globalization;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.Core.Camera;

public enum CameraPixelFormat
{
    Bgra8888
}

public sealed record class CameraFrame(
    CameraPixelFormat PixelFormat,
    int Width,
    int Height,
    int Stride,
    byte[] Buffer,
    DateTimeOffset Timestamp);

public sealed class CameraFrameArrivedEventArgs : EventArgs
{
    public CameraFrameArrivedEventArgs(CameraFrame frame)
    {
        Frame = frame;
    }

    public CameraFrame Frame { get; }
}

public enum CameraStatus
{
    Idle,
    Searching,
    Streaming,
    Disconnected,
    Error
}

public sealed class CameraStatusChangedEventArgs : EventArgs
{
    public CameraStatusChangedEventArgs(CameraStatus status, string message, CameraDeviceDescriptor? device)
    {
        Status = status;
        Message = message;
        Device = device;
    }

    public CameraStatus Status { get; }

    public string Message { get; }

    public CameraDeviceDescriptor? Device { get; }
}

public sealed record class CameraDeviceDescriptor(
    string DeviceId,
    int Index,
    string DisplayName,
    CameraResolution? NativeResolution)
{
    public static CameraDeviceDescriptor Auto { get; } = new("auto", -1, "Auto-Detect", null);

    public static CameraDeviceDescriptor Create(int index, CameraResolution? resolution)
    {
        var label = $"Camera {index.ToString(CultureInfo.InvariantCulture)}";
        return new CameraDeviceDescriptor(index.ToString(CultureInfo.InvariantCulture), index, label, resolution);
    }
}

public sealed record class CameraCaptureRequest(
    string DeviceId,
    CameraResolution Resolution,
    double FrameRate,
    bool IsMirrored)
{
    public static CameraCaptureRequest FromProfile(CameraProfile? profile)
    {
        profile ??= new CameraProfile();
        var deviceId = string.IsNullOrWhiteSpace(profile.DeviceId) ? "auto" : profile.DeviceId;
        var resolution = profile.Resolution ?? new CameraResolution();
        var fps = profile.FrameRate <= 0 ? 30d : profile.FrameRate;
        return new CameraCaptureRequest(deviceId, resolution, fps, profile.IsMirrored);
    }
}
