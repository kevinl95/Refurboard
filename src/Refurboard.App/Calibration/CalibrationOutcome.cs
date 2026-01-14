using System.Collections.Generic;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.App.Calibration;

public sealed record class CalibrationOutcome(
    IReadOnlyList<CornerObservation> Corners,
    int ScreenWidth,
    int ScreenHeight);
