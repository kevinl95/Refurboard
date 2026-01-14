using System;
using System.Collections.Generic;
using System.Linq;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Refurboard.Core.Configuration.Models;

namespace Refurboard.App.Controls;

public sealed class CalibrationOverlayControl : Control
{
    private static readonly string[] CornerOrder =
    {
        "TopLeft",
        "TopRight",
        "BottomRight",
        "BottomLeft"
    };

    private static readonly IBrush DefaultBackground = new SolidColorBrush(Color.Parse("#151b2b"));
    private static readonly IBrush DefaultFill = new SolidColorBrush(Color.Parse("#f8fafc"), 0.25);
    private static readonly IBrush DefaultStroke = new SolidColorBrush(Color.Parse("#f8fafc"));

    public static readonly StyledProperty<IReadOnlyList<CornerObservation>> CalibrationPointsProperty =
        AvaloniaProperty.Register<CalibrationOverlayControl, IReadOnlyList<CornerObservation>>(nameof(CalibrationPoints),
            Array.Empty<CornerObservation>());

    public static readonly StyledProperty<IBrush?> BackgroundBrushProperty =
        AvaloniaProperty.Register<CalibrationOverlayControl, IBrush?>(nameof(BackgroundBrush));

    public static readonly StyledProperty<IBrush?> FillBrushProperty =
        AvaloniaProperty.Register<CalibrationOverlayControl, IBrush?>(nameof(FillBrush));

    public static readonly StyledProperty<IBrush?> StrokeBrushProperty =
        AvaloniaProperty.Register<CalibrationOverlayControl, IBrush?>(nameof(StrokeBrush));

    public static readonly StyledProperty<double> StrokeThicknessProperty =
        AvaloniaProperty.Register<CalibrationOverlayControl, double>(nameof(StrokeThickness), 3d);

    public IReadOnlyList<CornerObservation> CalibrationPoints
    {
        get => GetValue(CalibrationPointsProperty);
        set => SetValue(CalibrationPointsProperty, value);
    }

    public IBrush? BackgroundBrush
    {
        get => GetValue(BackgroundBrushProperty);
        set => SetValue(BackgroundBrushProperty, value);
    }

    public IBrush? FillBrush
    {
        get => GetValue(FillBrushProperty);
        set => SetValue(FillBrushProperty, value);
    }

    public IBrush? StrokeBrush
    {
        get => GetValue(StrokeBrushProperty);
        set => SetValue(StrokeBrushProperty, value);
    }

    public double StrokeThickness
    {
        get => GetValue(StrokeThicknessProperty);
        set => SetValue(StrokeThicknessProperty, value);
    }

    public override void Render(DrawingContext context)
    {
        base.Render(context);

        var bounds = Bounds;
        var background = BackgroundBrush ?? DefaultBackground;
        if (background is not null)
        {
            context.FillRectangle(background, bounds);
        }

        var polygon = BuildPolygonPoints(bounds.Size);
        if (polygon.Count < 3)
        {
            return;
        }

        var geometry = new StreamGeometry();
        using (var geometryContext = geometry.Open())
        {
            geometryContext.BeginFigure(polygon[0], true);
            for (var i = 1; i < polygon.Count; i++)
            {
                geometryContext.LineTo(polygon[i]);
            }
            geometryContext.EndFigure(true);
        }

        var fill = FillBrush ?? DefaultFill;
        var strokeBrush = StrokeBrush ?? DefaultStroke;
        var stroke = new Pen(strokeBrush, StrokeThickness);
        context.DrawGeometry(fill, stroke, geometry);
    }

    private List<Point> BuildPolygonPoints(Size size)
    {
        var list = new List<Point>();
        if (CalibrationPoints is null)
        {
            return list;
        }

        foreach (var key in CornerOrder)
        {
            var match = CalibrationPoints.FirstOrDefault(c => string.Equals(c.Name, key, StringComparison.OrdinalIgnoreCase));
            if (match is null)
            {
                return new List<Point>();
            }

            var normalized = match.Normalized;
            var x = normalized?.X ?? 0;
            var y = normalized?.Y ?? 0;
            list.Add(new Point(x * size.Width, y * size.Height));
        }

        return list;
    }
}
