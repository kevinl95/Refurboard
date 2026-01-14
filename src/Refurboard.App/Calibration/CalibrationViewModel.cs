using System;
using System.Collections.Generic;
using Avalonia;
using Avalonia.Layout;
using Refurboard.Core.Configuration.Models;
using Refurboard.App.ViewModels;

namespace Refurboard.App.Calibration;

public sealed class CalibrationViewModel : ViewModelBase
{
    private sealed record CalibrationStep(string Name, HorizontalAlignment Horizontal, VerticalAlignment Vertical);

    private static readonly CalibrationStep[] Steps =
    {
        new("TopLeft", HorizontalAlignment.Left, VerticalAlignment.Top),
        new("TopRight", HorizontalAlignment.Right, VerticalAlignment.Top),
        new("BottomRight", HorizontalAlignment.Right, VerticalAlignment.Bottom),
        new("BottomLeft", HorizontalAlignment.Left, VerticalAlignment.Bottom)
    };

    private readonly List<CornerObservation> _observations = new();
    private int _currentIndex;

    public string Instruction => IsComplete
        ? "Calibration complete"
        : $"Tap the {CurrentStepLabel} target ({_currentIndex + 1}/4)";

    public HorizontalAlignment TargetHorizontalAlignment => CurrentStep.Horizontal;

    public VerticalAlignment TargetVerticalAlignment => CurrentStep.Vertical;

    public bool IsComplete => _currentIndex >= Steps.Length;

    public IEnumerable<CornerObservation> Observations => _observations;

    private CalibrationStep CurrentStep => IsComplete ? Steps[^1] : Steps[_currentIndex];

    private string CurrentStepLabel => CurrentStep.Name switch
    {
        "TopLeft" => "top-left",
        "TopRight" => "top-right",
        "BottomRight" => "bottom-right",
        "BottomLeft" => "bottom-left",
        _ => CurrentStep.Name
    };

    public void RecordPoint(Point point, Size bounds)
    {
        if (IsComplete)
        {
            return;
        }

        var clampedX = Math.Clamp(point.X, 0, bounds.Width);
        var clampedY = Math.Clamp(point.Y, 0, bounds.Height);
        var normalizedX = bounds.Width <= 0 ? 0 : clampedX / bounds.Width;
        var normalizedY = bounds.Height <= 0 ? 0 : clampedY / bounds.Height;

        var observation = new CornerObservation
        {
            Name = CurrentStep.Name,
            Pixel = new PixelCoordinate { X = clampedX, Y = clampedY },
            Normalized = new NormalizedCoordinate { X = normalizedX, Y = normalizedY }
        };

        _observations.Add(observation);
        _currentIndex++;
        RaisePropertyChanged(nameof(Instruction));
        RaisePropertyChanged(nameof(TargetHorizontalAlignment));
        RaisePropertyChanged(nameof(TargetVerticalAlignment));

        if (IsComplete)
        {
            Completed?.Invoke(this, EventArgs.Empty);
        }
    }

    public CalibrationOutcome ToOutcome(Size bounds)
    {
        return new CalibrationOutcome(
            _observations.AsReadOnly(),
            (int)Math.Round(bounds.Width),
            (int)Math.Round(bounds.Height));
    }

    public event EventHandler? Completed;
}
